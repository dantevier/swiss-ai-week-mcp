"""
Data resources for the mcp-swiss-info server.
"""

import json
from datetime import datetime
from typing import Any

from ..server import mcp
from ..utils.logger import setup_logger
from ..utils.validation import sanitize_input

logger = setup_logger("mcp_swiss_info.resources.data")

# In-memory data store for demo purposes
data_store: dict[str, Any] = {
    "example_1": {"name": "Sample Data", "value": 42, "created": datetime.now().isoformat()},
    "example_2": {
        "name": "Another Sample",
        "value": "Hello, World!",
        "created": datetime.now().isoformat(),
    },
}


@mcp.resource("data://store/{key}")
def get_stored_data(key: str) -> str:
    """Get data from the in-memory store by key."""
    try:
        sanitized_key = sanitize_input(key, max_length=100)

        if sanitized_key not in data_store:
            result = {
                "error": f"Key '{sanitized_key}' not found",
                "available_keys": list(data_store.keys()),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            result = {
                "key": sanitized_key,
                "data": data_store[sanitized_key],
                "timestamp": datetime.now().isoformat(),
            }

        logger.debug(f"Retrieved data for key: {sanitized_key}")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting stored data: {e}")
        raise


@mcp.resource("data://store")
def list_stored_data() -> str:
    """List all available data keys in the store."""
    try:
        result = {
            "keys": list(data_store.keys()),
            "count": len(data_store),
            "timestamp": datetime.now().isoformat(),
        }

        logger.debug(f"Listed {len(data_store)} data keys")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing stored data: {e}")
        raise


@mcp.resource("data://statistics")
def get_data_statistics() -> str:
    """Get statistics about the data store."""
    try:
        total_items = len(data_store)
        item_types: dict[str, int] = {}

        for key, value in data_store.items():
            if isinstance(value, dict) and "value" in value:
                value_type = type(value["value"]).__name__
                item_types[value_type] = item_types.get(value_type, 0) + 1

        result = {
            "total_items": total_items,
            "item_types": item_types,
            "memory_usage_estimate": len(json.dumps(data_store)),
            "timestamp": datetime.now().isoformat(),
        }

        logger.debug("Generated data statistics")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting data statistics: {e}")
        raise


@mcp.resource("data://sample/{format}")
def get_sample_data(format: str) -> str:
    """Get sample data in different formats."""
    try:
        sanitized_format = sanitize_input(format, max_length=20).lower()

        sample_data = {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
                {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
            ],
            "products": [
                {"id": 101, "name": "Widget A", "price": 19.99, "category": "widgets"},
                {"id": 102, "name": "Gadget B", "price": 29.99, "category": "gadgets"},
                {"id": 103, "name": "Tool C", "price": 39.99, "category": "tools"},
            ],
        }

        if sanitized_format == "json":
            result = json.dumps(sample_data, indent=2)
        elif sanitized_format == "csv":
            # Simple CSV conversion for demo
            csv_lines = ["id,name,email"]
            for user in sample_data["users"]:
                csv_lines.append(f"{user['id']},{user['name']},{user['email']}")
            result = "\n".join(csv_lines)
        elif sanitized_format == "xml":
            # Simple XML conversion for demo
            xml_lines = ["<users>"]
            for user in sample_data["users"]:
                xml_lines.append(f"  <user id=\"{user['id']}\">")
                xml_lines.append(f"    <name>{user['name']}</name>")
                xml_lines.append(f"    <email>{user['email']}</email>")
                xml_lines.append("  </user>")
            xml_lines.append("</users>")
            result = "\n".join(xml_lines)
        else:
            result = f"Unsupported format: {sanitized_format}. Available: json, csv, xml"

        logger.debug(f"Generated sample data in {sanitized_format} format")
        return result
    except Exception as e:
        logger.error(f"Error getting sample data: {e}")
        raise