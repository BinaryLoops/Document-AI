"""
Government Application Verification Demo Mode.
P15 requirement: Specialized interface for government application verification.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class GovernmentVerification:
    """
    Government Application Verification mode.
    Focuses on completeness, consistency, and readiness assessment.
    """
    
    def __init__(
        self,
        missing_checker,
        comparison_engine,
        readiness_calculator,
        review_queue
    ):
        """
        Initialize Government Verification mode.
        
        Args:
            missing_checker: MissingDocumentChecker instance
            comparison_engine: DocumentComparison instance
            readiness_calculator: ReadinessScoreCalculator instance
            review_queue: ReviewQueue instance
        """
        self.missing_checker = missing_checker
        self.comparison = comparison_engine
        self.readiness = readiness_calculator
        self.review_queue = review_queue
        logger.info("GovernmentVerification mode initialized")
    
    def verify_application(
        self,
        application_id: str,
        documents: List[Dict[str, Any]],
        workflow: str = "GOVERNMENT_APPLICATION"
    ) -> Dict[str, Any]:
        """
        Complete verification of a government application.
        
        Args:
            application_id: Application identifier
            documents: List of submitted documents
            workflow: Workflow type
            
        Returns:
            Comprehensive verification report
        """
        logger.info(f"Verifying government application: {application_id}")
        
        # Extract document types
        document_types = [doc.get('document_type', 'Unknown') for doc in documents]
        
        # Check for missing documents
        completeness = self.missing_checker.check_documents(
            document_types=document_types,
            workflow=workflow
        )
        
        # Check for inconsistencies
        inconsistencies = self.comparison.compare_documents(documents)
        
        # Collect all extracted fields
        all_fields = []
        for doc in documents:
            all_fields.extend(doc.get('extracted_fields', []))
        
        # Calculate readiness score
        readiness = self.readiness.calculate_readiness(
            completeness_result=completeness,
            inconsistencies=inconsistencies,
            extracted_fields=all_fields
        )
        
        # Route items to review queue
        review_items = self._route_to_review(
            application_id,
            documents,
            all_fields,
            inconsistencies
        )
        
        # Extract applicant information
        applicant_info = self._extract_applicant_info(documents)
        
        # Generate verification decision
        decision = self._generate_verification_decision(
            readiness,
            completeness,
            inconsistencies
        )
        
        return {
            'application_id': application_id,
            'workflow': workflow,
            'applicant_info': applicant_info,
            'document_count': len(documents),
            'completeness': completeness,
            'inconsistencies': {
                'total': len(inconsistencies),
                'by_severity': self._count_by_severity(inconsistencies),
                'details': inconsistencies
            },
            'readiness': readiness,
            'review_items': {
                'total': len(review_items),
                'pending': len([r for r in review_items if r.get('status') == 'PENDING'])
            },
            'verification_decision': decision
        }
    
    def check_identity_verification(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Verify identity documents specifically.
        
        Args:
            documents: List of identity-related documents
            
        Returns:
            Identity verification report
        """
        identity_docs = [
            doc for doc in documents
            if doc.get('document_type') in ['Identity Proof', 'Address Proof']
        ]
        
        if not identity_docs:
            return {
                'status': 'MISSING',
                'message': 'No identity documents found'
            }
        
        # Extract key identity fields
        identity_fields = {}
        for doc in identity_docs:
            for field in doc.get('extracted_fields', []):
                field_name = field.get('field')
                if field_name in ['full_name', 'date_of_birth', 'address', 'document_number']:
                    if field_name not in identity_fields:
                        identity_fields[field_name] = []
                    identity_fields[field_name].append({
                        'value': field.get('value'),
                        'confidence': field.get('confidence'),
                        'source': doc.get('filename')
                    })
        
        # Check consistency across identity documents
        consistency_check = {}
        for field_name, values in identity_fields.items():
            if len(values) > 1:
                # Check if all values are consistent
                unique_values = set(str(v['value']) for v in values)
                consistency_check[field_name] = {
                    'consistent': len(unique_values) == 1,
                    'values': list(unique_values),
                    'sources': [v['source'] for v in values]
                }
        
        return {
            'status': 'VERIFIED' if not consistency_check else 'NEEDS_REVIEW',
            'identity_documents': len(identity_docs),
            'extracted_fields': identity_fields,
            'consistency_check': consistency_check
        }
    
    def _extract_applicant_info(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract applicant information from documents."""
        applicant_info = {}
        
        # Look for application document
        app_doc = next(
            (doc for doc in documents if doc.get('document_type') == 'Application'),
            None
        )
        
        if app_doc:
            fields = app_doc.get('extracted_fields', [])
            field_map = {
                'applicant_name': 'name',
                'application_number': 'application_number',
                'date_filed': 'date_filed',
                'purpose': 'purpose',
                'contact_number': 'contact',
                'email': 'email'
            }
            
            for field in fields:
                field_name = field.get('field')
                if field_name in field_map:
                    applicant_info[field_map[field_name]] = field.get('value')
        
        return applicant_info
    
    def _route_to_review(
        self,
        application_id: str,
        documents: List[Dict[str, Any]],
        all_fields: List[Dict[str, Any]],
        inconsistencies: List[Dict[str, Any]]
    ) -> List[str]:
        """Route items to review queue."""
        review_ids = []
        
        # Route low-confidence fields
        for doc in documents:
            doc_id = doc.get('document_id')
            fields = doc.get('extracted_fields', [])
            
            field_review_ids = self.review_queue.route_extracted_fields(
                case_id=application_id,
                document_id=doc_id,
                extracted_fields=fields
            )
            review_ids.extend(field_review_ids)
        
        # Route inconsistencies
        if inconsistencies:
            inconsistency_review_ids = self.review_queue.route_inconsistencies(
                case_id=application_id,
                inconsistencies=inconsistencies
            )
            review_ids.extend(inconsistency_review_ids)
        
        return review_ids
    
    def _generate_verification_decision(
        self,
        readiness: Dict[str, Any],
        completeness: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate final verification decision."""
        score = readiness.get('overall_score', 0)
        level = readiness.get('readiness_level', 'NOT_READY')
        
        # Determine decision
        if score >= 90 and not inconsistencies and completeness['overall_status'] == 'COMPLETE':
            decision = 'APPROVED_FOR_REVIEW'
            message = 'Application meets all requirements and is ready for authorized review'
        elif score >= 75:
            decision = 'CONDITIONAL_APPROVAL'
            message = 'Application mostly complete but has minor issues requiring attention'
        elif score >= 60:
            decision = 'REQUIRES_CORRECTION'
            message = 'Application has significant issues that must be corrected'
        else:
            decision = 'REJECTED'
            message = 'Application does not meet minimum requirements'
        
        return {
            'decision': decision,
            'message': message,
            'score': score,
            'level': level,
            'next_steps': self._get_next_steps(decision, readiness, completeness)
        }
    
    @staticmethod
    def _count_by_severity(inconsistencies: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count inconsistencies by severity."""
        counts = {'MINOR': 0, 'MODERATE': 0, 'MAJOR': 0}
        for inc in inconsistencies:
            severity = inc.get('severity', 'MODERATE')
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    @staticmethod
    def _get_next_steps(
        decision: str,
        readiness: Dict[str, Any],
        completeness: Dict[str, Any]
    ) -> List[str]:
        """Generate next steps based on decision."""
        steps = []
        
        if decision == 'APPROVED_FOR_REVIEW':
            steps.append('Forward to authorized reviewer for final approval')
            steps.append('Notify applicant of review status')
        elif decision == 'CONDITIONAL_APPROVAL':
            steps.append('Review items in the review queue')
            steps.append('Correct minor inconsistencies')
            steps.append('Resubmit for final approval')
        elif decision == 'REQUIRES_CORRECTION':
            missing = completeness.get('missing_required', [])
            if missing:
                steps.append(f'Submit missing documents: {", ".join(missing)}')
            steps.append('Resolve all major inconsistencies')
            steps.append('Improve data quality for low-confidence fields')
        else:  # REJECTED
            steps.append('Review all application requirements')
            steps.append('Ensure all required documents are submitted')
            steps.append('Verify information accuracy')
            steps.append('Resubmit application')
        
        return steps
