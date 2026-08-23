"""
Verification and Readiness Score Calculator.
P11 requirement: Compute transparent score from completeness, consistency, confidence.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ReadinessScoreCalculator:
    """
    Calculate document verification readiness score.
    Combines completeness, consistency, and confidence metrics.
    """
    
    # Score weights (must sum to 1.0)
    WEIGHT_COMPLETENESS = 0.40  # Document completeness (P8)
    WEIGHT_CONSISTENCY = 0.30   # Cross-document consistency (P7)
    WEIGHT_CONFIDENCE = 0.30    # Field extraction confidence (P4)
    
    def __init__(self):
        """Initialize readiness score calculator."""
        logger.info("ReadinessScoreCalculator initialized")
    
    def calculate_readiness(
        self,
        completeness_result: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]],
        extracted_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate overall readiness score.
        
        Args:
            completeness_result: Result from MissingDocumentChecker
            inconsistencies: List from DocumentComparison
            extracted_fields: List of all extracted fields with confidence
            
        Returns:
            Readiness report with score and breakdown
        """
        # Calculate component scores
        completeness_score = self._calculate_completeness_score(completeness_result)
        consistency_score = self._calculate_consistency_score(inconsistencies)
        confidence_score = self._calculate_confidence_score(extracted_fields)
        
        # Calculate weighted overall score
        overall_score = (
            self.WEIGHT_COMPLETENESS * completeness_score +
            self.WEIGHT_CONSISTENCY * consistency_score +
            self.WEIGHT_CONFIDENCE * confidence_score
        )
        
        # Determine readiness level
        readiness_level = self._determine_readiness_level(overall_score)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            overall_score,
            completeness_score,
            consistency_score,
            confidence_score,
            completeness_result,
            inconsistencies
        )
        
        return {
            'overall_score': round(overall_score, 1),
            'readiness_level': readiness_level,
            'component_scores': {
                'completeness': round(completeness_score, 1),
                'consistency': round(consistency_score, 1),
                'confidence': round(confidence_score, 1)
            },
            'weights': {
                'completeness': self.WEIGHT_COMPLETENESS,
                'consistency': self.WEIGHT_CONSISTENCY,
                'confidence': self.WEIGHT_CONFIDENCE
            },
            'recommendation': recommendation,
            'details': {
                'missing_documents': completeness_result.get('missing_required', []),
                'inconsistency_count': len(inconsistencies),
                'major_inconsistencies': len([i for i in inconsistencies if i.get('severity') == 'MAJOR']),
                'low_confidence_fields': len([f for f in extracted_fields if f.get('confidence', 0) < 0.7])
            }
        }
    
    def _calculate_completeness_score(
        self,
        completeness_result: Dict[str, Any]
    ) -> float:
        """
        Calculate completeness score from P8 result.
        
        Returns:
            Score from 0-100
        """
        # Use the completeness percentage from missing document checker
        return completeness_result.get('completeness_percentage', 0.0)
    
    def _calculate_consistency_score(
        self,
        inconsistencies: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate consistency score from P7 inconsistencies.
        
        Returns:
            Score from 0-100
        """
        if not inconsistencies:
            return 100.0
        
        # Penalty per inconsistency based on severity
        penalty_map = {
            'MINOR': 3,
            'MODERATE': 8,
            'MAJOR': 15
        }
        
        total_penalty = sum(
            penalty_map.get(inc.get('severity', 'MODERATE'), 8)
            for inc in inconsistencies
        )
        
        # Cap at 100 penalty
        total_penalty = min(total_penalty, 100)
        
        return max(0.0, 100.0 - total_penalty)
    
    def _calculate_confidence_score(
        self,
        extracted_fields: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate average confidence from P4 extracted fields.
        
        Returns:
            Score from 0-100
        """
        if not extracted_fields:
            return 0.0
        
        # Get confidence values
        confidences = [
            f.get('confidence', 0.0) * 100
            for f in extracted_fields
            if f.get('value') is not None
        ]
        
        if not confidences:
            return 0.0
        
        return sum(confidences) / len(confidences)
    
    def _determine_readiness_level(self, score: float) -> str:
        """
        Determine readiness level from score.
        
        Returns:
            Readiness level string
        """
        if score >= 90:
            return "READY_FOR_REVIEW"
        elif score >= 75:
            return "MOSTLY_READY"
        elif score >= 60:
            return "NEEDS_ATTENTION"
        elif score >= 40:
            return "SIGNIFICANT_ISSUES"
        else:
            return "NOT_READY"
    
    def _generate_recommendation(
        self,
        overall_score: float,
        completeness_score: float,
        consistency_score: float,
        confidence_score: float,
        completeness_result: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]]
    ) -> str:
        """Generate human-readable recommendation."""
        recommendations = []
        
        # Check completeness
        if completeness_score < 100:
            missing = completeness_result.get('missing_required', [])
            if missing:
                recommendations.append(
                    f"Missing required documents: {', '.join(missing)}"
                )
        
        # Check consistency
        if consistency_score < 80:
            major = [i for i in inconsistencies if i.get('severity') == 'MAJOR']
            if major:
                recommendations.append(
                    f"Found {len(major)} major inconsistencies requiring resolution"
                )
        
        # Check confidence
        if confidence_score < 70:
            recommendations.append(
                "Multiple fields have low confidence - manual verification recommended"
            )
        
        # Overall recommendation
        if overall_score >= 90:
            status = "Ready for human/authorized review"
        elif overall_score >= 75:
            status = "Minor issues to address before review"
        elif overall_score >= 60:
            status = "Several issues need attention"
        else:
            status = "Significant work required before submission"
        
        if recommendations:
            return f"{status}. {' '.join(recommendations)}"
        else:
            return status
    
    def batch_calculate(
        self,
        cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate readiness scores for multiple cases.
        
        Args:
            cases: List of cases with required data
            
        Returns:
            List of readiness reports
        """
        results = []
        
        for case in cases:
            try:
                result = self.calculate_readiness(
                    completeness_result=case.get('completeness_result', {}),
                    inconsistencies=case.get('inconsistencies', []),
                    extracted_fields=case.get('extracted_fields', [])
                )
                result['case_id'] = case.get('case_id')
                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating readiness for case {case.get('case_id')}: {e}")
                results.append({
                    'case_id': case.get('case_id'),
                    'overall_score': 0.0,
                    'readiness_level': 'ERROR',
                    'recommendation': f'Error calculating score: {str(e)}'
                })
        
        return results
