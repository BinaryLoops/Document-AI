"""
Notary/Affidavit Assistant Demo Mode.
P15 requirement: Specialized interface for notary and affidavit processing.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NotaryAssistant:
    """
    Notary/Affidavit Assistant mode.
    Helps with identity verification, document preparation, and consistency checks.
    """
    
    def __init__(
        self,
        comparison_engine,
        missing_checker
    ):
        """
        Initialize Notary Assistant mode.
        
        Args:
            comparison_engine: DocumentComparison instance
            missing_checker: MissingDocumentChecker instance
        """
        self.comparison = comparison_engine
        self.missing_checker = missing_checker
        logger.info("NotaryAssistant mode initialized")
    
    def verify_affidavit_package(
        self,
        affidavit_id: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Verify complete affidavit package with supporting documents.
        
        Args:
            affidavit_id: Affidavit identifier
            documents: List of documents (affidavit + supporting)
            
        Returns:
            Verification report
        """
        logger.info(f"Verifying affidavit package: {affidavit_id}")
        
        # Find affidavit document
        affidavit_doc = next(
            (doc for doc in documents if doc.get('document_type') == 'Affidavit'),
            None
        )
        
        if not affidavit_doc:
            return {
                'status': 'ERROR',
                'message': 'No affidavit document found in package'
            }
        
        # Extract affidavit details
        affidavit_details = self._extract_affidavit_details(affidavit_doc)
        
        # Check supporting documents
        document_types = [doc.get('document_type') for doc in documents]
        completeness = self.missing_checker.check_documents(
            document_types=document_types,
            workflow='NOTARY_VERIFICATION'
        )
        
        # Verify identity consistency
        identity_check = self._verify_identity_consistency(documents)
        
        # Check for inconsistencies
        inconsistencies = self.comparison.compare_documents(documents)
        
        # Generate notarization checklist
        checklist = self._generate_notarization_checklist(
            affidavit_details,
            identity_check,
            completeness,
            inconsistencies
        )
        
        # Prepare draft package
        draft_package = self._prepare_draft_package(
            affidavit_doc,
            documents,
            affidavit_details
        )
        
        return {
            'affidavit_id': affidavit_id,
            'affidavit_details': affidavit_details,
            'document_count': len(documents),
            'completeness': completeness,
            'identity_verification': identity_check,
            'inconsistencies': inconsistencies,
            'notarization_checklist': checklist,
            'draft_package': draft_package,
            'ready_for_notarization': self._is_ready_for_notarization(
                identity_check,
                completeness,
                inconsistencies
            )
        }
    
    def extract_deponent_info(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract deponent information from documents.
        
        Args:
            documents: List of documents
            
        Returns:
            Deponent information
        """
        deponent_info = {
            'name': None,
            'address': None,
            'identification': [],
            'contact': None
        }
        
        for doc in documents:
            fields = doc.get('extracted_fields', [])
            
            for field in fields:
                field_name = field.get('field', '').lower()
                value = field.get('value')
                confidence = field.get('confidence', 0)
                
                if confidence > 0.7 and value:
                    if 'deponent_name' in field_name or 'full_name' in field_name:
                        deponent_info['name'] = value
                    elif 'address' in field_name:
                        deponent_info['address'] = value
                    elif 'document_number' in field_name or 'identification' in field_name:
                        deponent_info['identification'].append({
                            'type': doc.get('document_type', 'Unknown'),
                            'number': value
                        })
                    elif 'contact' in field_name or 'phone' in field_name:
                        deponent_info['contact'] = value
        
        return deponent_info
    
    def _extract_affidavit_details(
        self,
        affidavit_doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract key details from affidavit document."""
        details = {}
        fields = affidavit_doc.get('extracted_fields', [])
        
        field_map = {
            'deponent_name': 'deponent_name',
            'statement_date': 'statement_date',
            'notary_name': 'notary_name',
            'purpose': 'purpose',
            'case_reference': 'case_reference'
        }
        
        for field in fields:
            field_name = field.get('field')
            if field_name in field_map:
                details[field_map[field_name]] = {
                    'value': field.get('value'),
                    'confidence': field.get('confidence')
                }
        
        return details
    
    def _verify_identity_consistency(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify identity information is consistent across documents."""
        # Extract identity fields from all documents
        identity_data = {}
        
        for doc in documents:
            for field in doc.get('extracted_fields', []):
                field_name = field.get('field', '').lower()
                
                # Focus on identity fields
                if any(key in field_name for key in ['name', 'address', 'dob', 'date_of_birth']):
                    if field_name not in identity_data:
                        identity_data[field_name] = []
                    
                    identity_data[field_name].append({
                        'value': field.get('value'),
                        'source': doc.get('filename'),
                        'confidence': field.get('confidence')
                    })
        
        # Check consistency
        consistency_results = {}
        for field_name, values in identity_data.items():
            if len(values) > 1:
                unique_values = set(str(v['value']) for v in values if v['value'])
                consistency_results[field_name] = {
                    'consistent': len(unique_values) <= 1,
                    'unique_values': list(unique_values),
                    'sources': [v['source'] for v in values]
                }
        
        all_consistent = all(r['consistent'] for r in consistency_results.values())
        
        return {
            'status': 'CONSISTENT' if all_consistent else 'INCONSISTENT',
            'all_consistent': all_consistent,
            'details': consistency_results
        }
    
    def _generate_notarization_checklist(
        self,
        affidavit_details: Dict[str, Any],
        identity_check: Dict[str, Any],
        completeness: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate checklist for notarization."""
        checklist = []
        
        # Check deponent identity
        if affidavit_details.get('deponent_name'):
            checklist.append({
                'item': 'Deponent name verified',
                'status': '✓',
                'notes': f"Name: {affidavit_details['deponent_name'].get('value')}"
            })
        else:
            checklist.append({
                'item': 'Deponent name verified',
                'status': '✗',
                'notes': 'Deponent name not found or unclear'
            })
        
        # Check supporting documents
        if completeness.get('overall_status') == 'COMPLETE':
            checklist.append({
                'item': 'Supporting documents complete',
                'status': '✓',
                'notes': 'All required documents present'
            })
        else:
            missing = completeness.get('missing_required', [])
            checklist.append({
                'item': 'Supporting documents complete',
                'status': '✗',
                'notes': f"Missing: {', '.join(missing)}"
            })
        
        # Check identity consistency
        if identity_check.get('all_consistent'):
            checklist.append({
                'item': 'Identity information consistent',
                'status': '✓',
                'notes': 'No discrepancies found'
            })
        else:
            checklist.append({
                'item': 'Identity information consistent',
                'status': '⚠',
                'notes': 'Minor discrepancies detected - review required'
            })
        
        # Check for major inconsistencies
        major_issues = [i for i in inconsistencies if i.get('severity') == 'MAJOR']
        if not major_issues:
            checklist.append({
                'item': 'No major inconsistencies',
                'status': '✓',
                'notes': 'Document integrity verified'
            })
        else:
            checklist.append({
                'item': 'No major inconsistencies',
                'status': '✗',
                'notes': f"{len(major_issues)} major issues require resolution"
            })
        
        return checklist
    
    def _prepare_draft_package(
        self,
        affidavit_doc: Dict[str, Any],
        all_documents: List[Dict[str, Any]],
        affidavit_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare draft notarization package."""
        return {
            'status': 'DRAFT',
            'label': 'DRAFT - FOR REVIEW ONLY - NOT NOTARIZED',
            'affidavit_filename': affidavit_doc.get('filename'),
            'supporting_documents': [
                doc.get('filename')
                for doc in all_documents
                if doc.get('document_type') != 'Affidavit'
            ],
            'deponent': affidavit_details.get('deponent_name', {}).get('value', 'Unknown'),
            'prepared_date': datetime.utcnow().isoformat(),
            'warning': 'This is a DRAFT package. Human verification and authorized notarization required before legal use.'
        }
    
    @staticmethod
    def _is_ready_for_notarization(
        identity_check: Dict[str, Any],
        completeness: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Determine if package is ready for notarization."""
        ready = (
            identity_check.get('all_consistent', False) and
            completeness.get('overall_status') == 'COMPLETE' and
            len([i for i in inconsistencies if i.get('severity') == 'MAJOR']) == 0
        )
        
        if ready:
            return {
                'ready': True,
                'message': 'Package is ready for human review and notarization',
                'next_step': 'Forward to authorized notary for final verification and signing'
            }
        else:
            issues = []
            if not identity_check.get('all_consistent'):
                issues.append('Identity inconsistencies must be resolved')
            if completeness.get('overall_status') != 'COMPLETE':
                issues.append('Missing required supporting documents')
            if [i for i in inconsistencies if i.get('severity') == 'MAJOR']:
                issues.append('Major inconsistencies must be corrected')
            
            return {
                'ready': False,
                'message': 'Package requires corrections before notarization',
                'issues': issues
            }
