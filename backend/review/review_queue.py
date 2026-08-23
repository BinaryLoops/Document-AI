"""
Human Review Queue System.
P12 requirement: Route low-confidence items for manual review.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ReviewQueue:
    """
    Manage queue of items requiring human review.
    Routes low-confidence extractions to review interface.
    """
    
    # Confidence thresholds
    THRESHOLD_LOW = 0.70
    THRESHOLD_MEDIUM = 0.90
    THRESHOLD_HIGH = 1.00
    
    def __init__(self, storage_backend=None):
        """
        Initialize review queue.
        
        Args:
            storage_backend: Storage backend (Firestore/MongoDB)
        """
        self.storage = storage_backend
        self.queue = []  # In-memory queue
        logger.info("ReviewQueue initialized")
    
    def add_to_queue(
        self,
        case_id: str,
        document_id: str,
        item_type: str,
        item_data: Dict[str, Any],
        confidence: float,
        priority: Optional[str] = None
    ) -> str:
        """
        Add an item to the review queue.
        
        Args:
            case_id: Case identifier
            document_id: Document identifier
            item_type: Type of item (FIELD, CLASSIFICATION, COMPARISON, etc.)
            item_data: Data about the item
            confidence: Confidence score
            priority: Optional priority override
            
        Returns:
            Review item ID
        """
        review_id = str(uuid.uuid4())
        
        # Determine priority based on confidence if not provided
        if priority is None:
            priority = self._determine_priority(confidence)
        
        review_item = {
            'review_id': review_id,
            'case_id': case_id,
            'document_id': document_id,
            'item_type': item_type,
            'item_data': item_data,
            'confidence': confidence,
            'priority': priority,
            'status': 'PENDING',
            'created_at': datetime.utcnow().isoformat(),
            'reviewed_at': None,
            'reviewer': None,
            'decision': None,
            'comments': None
        }
        
        self.queue.append(review_item)
        
        # Persist to storage
        if self.storage:
            self._save_to_storage(review_item)
        
        logger.info(f"Added item to review queue: {review_id} (priority: {priority})")
        return review_id
    
    def route_extracted_fields(
        self,
        case_id: str,
        document_id: str,
        extracted_fields: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Route extracted fields to review queue based on confidence.
        
        Args:
            case_id: Case identifier
            document_id: Document identifier
            extracted_fields: List of extracted fields
            
        Returns:
            List of review IDs created
        """
        review_ids = []
        
        for field in extracted_fields:
            confidence = field.get('confidence', 0.0)
            
            # Only route if below high threshold
            if confidence < self.THRESHOLD_HIGH:
                review_id = self.add_to_queue(
                    case_id=case_id,
                    document_id=document_id,
                    item_type='FIELD_EXTRACTION',
                    item_data={
                        'field_name': field.get('field'),
                        'extracted_value': field.get('value'),
                        'evidence': field.get('evidence'),
                        'field_type': field.get('field_type'),
                        'required': field.get('required')
                    },
                    confidence=confidence
                )
                review_ids.append(review_id)
        
        logger.info(f"Routed {len(review_ids)} fields to review queue")
        return review_ids
    
    def route_inconsistencies(
        self,
        case_id: str,
        inconsistencies: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Route document inconsistencies to review queue.
        
        Args:
            case_id: Case identifier
            inconsistencies: List from DocumentComparison
            
        Returns:
            List of review IDs created
        """
        review_ids = []
        
        for inconsistency in inconsistencies:
            # Severity to confidence mapping
            severity_confidence_map = {
                'MINOR': 0.85,
                'MODERATE': 0.65,
                'MAJOR': 0.40
            }
            
            confidence = severity_confidence_map.get(
                inconsistency.get('severity', 'MODERATE'),
                0.65
            )
            
            review_id = self.add_to_queue(
                case_id=case_id,
                document_id=inconsistency.get('document_a', {}).get('document_id', 'unknown'),
                item_type='INCONSISTENCY',
                item_data={
                    'severity': inconsistency.get('severity'),
                    'field_name': inconsistency.get('field_name'),
                    'document_a': inconsistency.get('document_a'),
                    'document_b': inconsistency.get('document_b'),
                    'similarity_score': inconsistency.get('similarity_score'),
                    'message': inconsistency.get('message')
                },
                confidence=confidence
            )
            review_ids.append(review_id)
        
        logger.info(f"Routed {len(review_ids)} inconsistencies to review queue")
        return review_ids
    
    def get_pending_reviews(
        self,
        case_id: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get pending review items.
        
        Args:
            case_id: Filter by case ID
            priority: Filter by priority
            limit: Maximum items to return
            
        Returns:
            List of pending review items
        """
        pending = [item for item in self.queue if item['status'] == 'PENDING']
        
        # Apply filters
        if case_id:
            pending = [item for item in pending if item['case_id'] == case_id]
        if priority:
            pending = [item for item in pending if item['priority'] == priority]
        
        # Sort by priority (HIGH -> LOW) and creation time
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        pending.sort(key=lambda x: (
            priority_order.get(x['priority'], 3),
            x['created_at']
        ))
        
        return pending[:limit]
    
    def submit_review(
        self,
        review_id: str,
        decision: str,
        reviewer: str,
        corrected_value: Optional[Any] = None,
        comments: Optional[str] = None
    ) -> bool:
        """
        Submit a review decision.
        
        Args:
            review_id: Review item ID
            decision: Decision (ACCEPT, EDIT, REJECT)
            reviewer: Reviewer identifier
            corrected_value: Corrected value if decision is EDIT
            comments: Optional comments
            
        Returns:
            Success status
        """
        # Find review item
        review_item = next(
            (item for item in self.queue if item['review_id'] == review_id),
            None
        )
        
        if not review_item:
            logger.error(f"Review item not found: {review_id}")
            return False
        
        # Update review item
        review_item['status'] = 'REVIEWED'
        review_item['decision'] = decision
        review_item['reviewer'] = reviewer
        review_item['reviewed_at'] = datetime.utcnow().isoformat()
        review_item['comments'] = comments
        
        if corrected_value is not None:
            review_item['corrected_value'] = corrected_value
        
        # Persist changes
        if self.storage:
            self._update_storage(review_item)
        
        logger.info(f"Review submitted: {review_id} - {decision} by {reviewer}")
        return True
    
    def get_review_statistics(
        self,
        case_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get review queue statistics.
        
        Args:
            case_id: Optional case filter
            
        Returns:
            Statistics dictionary
        """
        items = self.queue
        if case_id:
            items = [item for item in items if item['case_id'] == case_id]
        
        pending = [item for item in items if item['status'] == 'PENDING']
        reviewed = [item for item in items if item['status'] == 'REVIEWED']
        
        # Count by priority
        priority_counts = {
            'HIGH': len([i for i in pending if i['priority'] == 'HIGH']),
            'MEDIUM': len([i for i in pending if i['priority'] == 'MEDIUM']),
            'LOW': len([i for i in pending if i['priority'] == 'LOW'])
        }
        
        # Count by decision
        decision_counts = {}
        for item in reviewed:
            decision = item.get('decision', 'UNKNOWN')
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        return {
            'total_items': len(items),
            'pending': len(pending),
            'reviewed': len(reviewed),
            'by_priority': priority_counts,
            'by_decision': decision_counts,
            'review_rate': len(reviewed) / len(items) if items else 0.0
        }
    
    def _determine_priority(self, confidence: float) -> str:
        """Determine priority based on confidence."""
        if confidence < self.THRESHOLD_LOW:
            return 'HIGH'
        elif confidence < self.THRESHOLD_MEDIUM:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _save_to_storage(self, review_item: Dict[str, Any]):
        """Save review item to storage."""
        try:
            if hasattr(self.storage, 'collection'):
                # Firestore
                self.storage.collection('review_queue').document(
                    review_item['review_id']
                ).set(review_item)
            elif hasattr(self.storage, 'insert_one'):
                # MongoDB
                self.storage.insert_one(review_item)
        except Exception as e:
            logger.error(f"Failed to save review item to storage: {e}")
    
    def _update_storage(self, review_item: Dict[str, Any]):
        """Update review item in storage."""
        try:
            if hasattr(self.storage, 'collection'):
                # Firestore
                self.storage.collection('review_queue').document(
                    review_item['review_id']
                ).update(review_item)
            elif hasattr(self.storage, 'update_one'):
                # MongoDB
                self.storage.update_one(
                    {'review_id': review_item['review_id']},
                    {'$set': review_item}
                )
        except Exception as e:
            logger.error(f"Failed to update review item in storage: {e}")
