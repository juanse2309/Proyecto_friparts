"""
database.py — Centralized SQL Database Configuration.
Google Sheets legacy support has been removed.
"""
import logging

logger = logging.getLogger(__name__)

# Legacy placeholder for SheetsClient to avoid broken imports during cleanup
class SheetsClient:
    def __init__(self):
        logger.warning("⚠️  [GSHEET] SheetsClient is deprecated and returns empty data.")
    def get_spreadsheet(self, *args, **kwargs): return None
    def get_worksheet(self, *args, **kwargs): return None
    def get_all_records_seguro(self, *args, **kwargs): return []

sheets_client = SheetsClient()
