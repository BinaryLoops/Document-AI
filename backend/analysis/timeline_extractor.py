"""
Case Timeline Extraction and Display.
P13 requirement: Extract dates from documents and display chronologically.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import datefinder

logger = logging.getLogger(__name__)


class TimelineExtractor:
    """
    Extract and organize dates from case documents into a chronological timeline.
    """
    
    def __init__(self):
        """Initialize timeline extractor."""
        logger.info("TimelineExtractor initialized")
    
    def extract_timeline(
        self,
        case_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract timeline from all documents in a case.
        
        Args:
            case_documents: List of documents with extracted fields
            
        Returns:
            Timeline data with chronologically sorted events
        """
        events = []
        
        for doc in case_documents:
            document_id = doc.get('document_id')
            filename = doc.get('filename', 'Unknown')
            extracted_fields = doc.get('extracted_fields', [])
            
            # Extract date fields
            date_events = self._extract_date_fields(
                extracted_fields,
                document_id,
                filename
            )
            events.extend(date_events)
        
        # Sort events chronologically
        events.sort(key=lambda x: x['date'])
        
        # Generate timeline summary
        timeline = {
            'total_events': len(events),
            'earliest_date': events[0]['date'] if events else None,
            'latest_date': events[-1]['date'] if events else None,
            'events': events,
            'timeline_span_days': self._calculate_span(events)
        }
        
        logger.info(f"Extracted timeline with {len(events)} events")
        return timeline
    
    def _extract_date_fields(
        self,
        extracted_fields: List[Dict[str, Any]],
        document_id: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Extract date events from extracted fields.
        
        Returns:
            List of date events
        """
        events = []
        
        # Date field names to look for
        date_field_names = [
            'date', 'date_of_birth', 'issue_date', 'expiry_date',
            'date_filed', 'statement_date', 'hearing_date', 'judgment_date',
            'invoice_date', 'due_date', 'contract_date', 'effective_date',
            'receipt_date', 'event_date', 'application_date'
        ]
        
        for field in extracted_fields:
            field_name = field.get('field', '')
            value = field.get('value')
            
            # Check if this is a date field
            if field_name.lower() in date_field_names and value:
                # Parse date
                parsed_date = self._parse_date(str(value))
                
                if parsed_date:
                    events.append({
                        'date': parsed_date,
                        'date_string': str(value),
                        'event_type': self._get_event_type(field_name),
                        'field_name': field_name,
                        'document_id': document_id,
                        'document_name': filename,
                        'confidence': field.get('confidence', 0.0),
                        'evidence': field.get('evidence', {})
                    })
        
        return events
    
    def _parse_date(self, date_string: str) -> Optional[str]:
        """
        Parse date string into ISO format.
        
        Returns:
            ISO format date string (YYYY-MM-DD) or None
        """
        # Try multiple parsing strategies
        
        # Strategy 1: Standard formats
        date_patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),  # YYYY-MM-DD
            (r'(\d{2})/(\d{2})/(\d{4})', '%d/%m/%Y'),  # DD/MM/YYYY
            (r'(\d{2})-(\d{2})-(\d{4})', '%d-%m-%Y'),  # DD-MM-YYYY
            (r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', '%d %B %Y'),  # DD Month YYYY
        ]
        
        for pattern, fmt in date_patterns:
            match = re.search(pattern, date_string)
            if match:
                try:
                    date_obj = datetime.strptime(date_string, fmt)
                    return date_obj.strftime('%Y-%m-%d')
                except:
                    pass
        
        # Strategy 2: Use datefinder for natural language dates
        try:
            matches = list(datefinder.find_dates(date_string))
            if matches:
                return matches[0].strftime('%Y-%m-%d')
        except:
            pass
        
        logger.warning(f"Could not parse date: {date_string}")
        return None
    
    def _get_event_type(self, field_name: str) -> str:
        """Map field name to event type."""
        event_type_map = {
            'date_of_birth': 'Birth',
            'issue_date': 'Issuance',
            'expiry_date': 'Expiration',
            'date_filed': 'Filing',
            'statement_date': 'Statement',
            'hearing_date': 'Hearing',
            'judgment_date': 'Judgment',
            'invoice_date': 'Invoice',
            'due_date': 'Due Date',
            'contract_date': 'Contract Signing',
            'effective_date': 'Effective Date',
            'receipt_date': 'Receipt',
            'event_date': 'Event',
            'application_date': 'Application'
        }
        
        return event_type_map.get(field_name.lower(), 'Date')
    
    def _calculate_span(self, events: List[Dict[str, Any]]) -> Optional[int]:
        """Calculate timeline span in days."""
        if len(events) < 2:
            return None
        
        try:
            earliest = datetime.fromisoformat(events[0]['date'])
            latest = datetime.fromisoformat(events[-1]['date'])
            return (latest - earliest).days
        except:
            return None
    
    def generate_timeline_text(
        self,
        timeline: Dict[str, Any],
        format_style: str = 'detailed'
    ) -> str:
        """
        Generate human-readable timeline text.
        
        Args:
            timeline: Timeline data
            format_style: 'detailed' or 'compact'
            
        Returns:
            Formatted timeline string
        """
        events = timeline.get('events', [])
        
        if not events:
            return "No timeline events found."
        
        lines = [
            "=" * 70,
            "CASE TIMELINE",
            "=" * 70,
            f"Total Events: {timeline['total_events']}",
            f"Date Range: {timeline['earliest_date']} to {timeline['latest_date']}",
            f"Span: {timeline['timeline_span_days']} days" if timeline['timeline_span_days'] else "",
            "",
            "CHRONOLOGICAL EVENTS:",
            "-" * 70
        ]
        
        for idx, event in enumerate(events, 1):
            if format_style == 'detailed':
                lines.extend([
                    f"\n{idx}. {event['date']} - {event['event_type']}",
                    f"   Document: {event['document_name']}",
                    f"   Field: {event['field_name']}",
                    f"   Value: {event['date_string']}",
                    f"   Confidence: {event['confidence']:.2f}"
                ])
            else:  # compact
                lines.append(
                    f"{idx}. {event['date']} | {event['event_type']} | "
                    f"{event['document_name']}"
                )
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)
    
    def filter_timeline(
        self,
        timeline: Dict[str, Any],
        event_types: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None,
        document_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Filter timeline events.
        
        Args:
            timeline: Original timeline
            event_types: Filter by event types
            date_range: Filter by date range {start, end}
            document_ids: Filter by document IDs
            
        Returns:
            Filtered timeline
        """
        events = timeline.get('events', [])
        filtered = events.copy()
        
        # Apply event type filter
        if event_types:
            filtered = [e for e in filtered if e['event_type'] in event_types]
        
        # Apply date range filter
        if date_range:
            start = date_range.get('start')
            end = date_range.get('end')
            if start:
                filtered = [e for e in filtered if e['date'] >= start]
            if end:
                filtered = [e for e in filtered if e['date'] <= end]
        
        # Apply document filter
        if document_ids:
            filtered = [e for e in filtered if e['document_id'] in document_ids]
        
        # Reconstruct timeline
        if filtered:
            return {
                'total_events': len(filtered),
                'earliest_date': filtered[0]['date'],
                'latest_date': filtered[-1]['date'],
                'events': filtered,
                'timeline_span_days': self._calculate_span(filtered)
            }
        else:
            return {
                'total_events': 0,
                'earliest_date': None,
                'latest_date': None,
                'events': [],
                'timeline_span_days': None
            }
