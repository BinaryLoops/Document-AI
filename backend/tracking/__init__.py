"""
tracking/ -- Government Document Tracking & Notification System.

Tracks the lifecycle of every document application through stages:
  Submitted → Verification → Officer Review → Issuing Authority →
  Generated → Printed → Dispatched → Delivered

Provides:
  - Real-time stage tracking with ETA
  - Full delivery history (audit trail)
  - Push notifications for every stage transition
  - Notification management (read/unread)
"""

__version__ = "1.0.0"
