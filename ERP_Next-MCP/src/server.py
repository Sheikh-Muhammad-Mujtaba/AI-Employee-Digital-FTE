import json
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        CallToolResult,
        ListToolsResult,
    )
    HAS_NOTIFICATION_OPTIONS = True
except ImportError:
    try:
        from mcp.server import Server
        from mcp.server.models import InitializationOptions
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent, CallToolResult, ListToolsResult
        HAS_NOTIFICATION_OPTIONS = False
    except ImportError as e:
        logger.error(f"MCP import failed: {e}")
        exit(1)

from .erpnext_client import ERPNextClient
from .permissions import PermissionManager

# Load configuration
config_path = Path(__file__).parent.parent / "config" / "config.json"
try:
    with open(config_path, "r") as f:
        CONFIG = json.load(f)
        logger.info(f"Config loaded from: {config_path}")
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    exit(1)

# Initialize components — credentials loaded from .env
# Priority: username+password (session auth) → API key+secret (token auth)
_url = os.environ.get("ERPNEXT_URL")
if not _url:
    logger.error("ERPNEXT_URL not set in .env")
    exit(1)

erpnext_client = ERPNextClient(
    url=_url,
    username=os.environ.get("ERPNEXT_USERNAME"),
    password=os.environ.get("ERPNEXT_PASSWORD"),
    api_key=os.environ.get("ERPNEXT_API_KEY"),
    api_secret=os.environ.get("ERPNEXT_API_SECRET"),
    config=CONFIG
)
permission_manager = PermissionManager(CONFIG)

# Create server
app = Server("mcp-server")


@app.list_tools()
async def list_tools() -> ListToolsResult:
    """List all available tools for ERPNext operations"""
    tools = []
    
    tools.extend([
        Tool(
            name="test_connection",
            description="Test connection to ERPNext server",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_system_info",
            description="Get ERPNext system information",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="list_doctypes",
            description="List all configured doctypes and their permissions",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_doctype_permissions",
            description="Get detailed permissions for a specific doctype",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {
                        "type": "string",
                        "description": "Name of the doctype to check permissions for"
                    }
                },
                "required": ["doctype"]
            }
        )
    ])
    
    configured_doctypes = permission_manager.get_all_doctypes()
    
    for doctype in configured_doctypes:
        allowed_ops = permission_manager.get_allowed_operations(doctype)
        
        if 'read' in allowed_ops:
            # List documents tool
            tools.append(Tool(
                name=f"list_{doctype.lower().replace(' ', '_')}_documents",
                description=f"List {doctype} documents with optional filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Filters to apply to the query"
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific fields to retrieve"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 20)",
                            "minimum": 1,
                            "maximum": 100
                        }
                    }
                }
            ))
            
            # Get document tool
            tools.append(Tool(
                name=f"get_{doctype.lower().replace(' ', '_')}_document",
                description=f"Get specific {doctype} document by name",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": f"Name/ID of the {doctype} document"
                        }
                    },
                    "required": ["name"]
                }
            ))
            
            # Search documents tool
            tools.append(Tool(
                name=f"search_{doctype.lower().replace(' ', '_')}_documents",
                description=f"Search {doctype} documents by text",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Text to search for in document names"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10)",
                            "minimum": 1,
                            "maximum": 50
                        }
                    },
                    "required": ["search_term"]
                }
            ))
        
        if 'create' in allowed_ops:
            tools.append(Tool(
                name=f"create_{doctype.lower().replace(' ', '_')}_document",
                description=f"Create new {doctype} document",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "object",
                            "description": f"Data for the new {doctype} document"
                        }
                    },
                    "required": ["data"]
                }
            ))
        
        if 'update' in allowed_ops:
            tools.append(Tool(
                name=f"update_{doctype.lower().replace(' ', '_')}_document",
                description=f"Update existing {doctype} document",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": f"Name/ID of the {doctype} document to update"
                        },
                        "data": {
                            "type": "object",
                            "description": "Updated data for the document"
                        }
                    },
                    "required": ["name", "data"]
                }
            ))
        
        if 'delete' in allowed_ops:
            tools.append(Tool(
                name=f"delete_{doctype.lower().replace(' ', '_')}_document",
                description=f"Delete {doctype} document",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": f"Name/ID of the {doctype} document to delete"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Confirmation flag for deletion"
                        }
                    },
                    "required": ["name", "confirm"]
                }
            ))
    
    tools.extend([
        Tool(
            name="get_generic_document",
            description="Get any document by doctype and name",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "description": "Document type"},
                    "name": {"type": "string", "description": "Document name/ID"}
                },
                "required": ["doctype", "name"]
            }
        ),
        Tool(
            name="list_generic_documents",
            description="List documents for any doctype",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "description": "Document type"},
                    "filters": {"type": "object", "description": "Filters to apply"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                },
                "required": ["doctype"]
            }
        ),
        Tool(
            name="create_generic_document",
            description="Create document for any doctype",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "description": "Document type"},
                    "data": {"type": "object", "description": "Document data"}
                },
                "required": ["doctype", "data"]
            }
        ),
        Tool(
            name="update_generic_document",
            description="Update document for any doctype",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "description": "Document type"},
                    "name": {"type": "string", "description": "Document name/ID"},
                    "data": {"type": "object", "description": "Updated data"}
                },
                "required": ["doctype", "name", "data"]
            }
        ),
        Tool(
            name="get_doctype_schema",
            description="Get schema/metadata for any doctype",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "description": "Document type"}
                },
                "required": ["doctype"]
            }
        )
    ])
    
    return ListToolsResult(tools=tools)


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle all tool calls for ERPNext operations"""
    
    try:
        if name == "test_connection":
            connected = await erpnext_client.test_connection()
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"ERPNext connection: {'✅ Connected' if connected else '❌ Failed'}"
                )]
            )
        
        elif name == "get_system_info":
            info = await erpnext_client.get_system_info()
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"ERPNext System Info:\n{json.dumps(info, indent=2)}"
                )]
            )
        
        elif name == "list_doctypes":
            doctypes = permission_manager.get_all_doctypes()
            summaries = []
            for doctype in doctypes:
                summary = permission_manager.get_doctype_summary(doctype)
                summaries.append(summary)
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Configured DocTypes:\n{json.dumps(summaries, indent=2)}"
                )]
            )
        
        elif name == "get_doctype_permissions":
            doctype = arguments.get("doctype")
            if not doctype:
                return CallToolResult(
                    content=[TextContent(type="text", text="❌ DocType parameter required")],
                    isError=True
                )
            
            summary = permission_manager.get_doctype_summary(doctype)
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Permissions for {doctype}:\n{json.dumps(summary, indent=2)}"
                )]
            )
        
        elif name == "get_generic_document":
            return await handle_get_document(
                arguments.get("doctype"),
                arguments.get("name")
            )
        
        elif name == "list_generic_documents":
            return await handle_list_documents(
                arguments.get("doctype"),
                arguments.get("filters"),
                arguments.get("fields"),
                arguments.get("limit", 20)
            )
        
        elif name == "create_generic_document":
            return await handle_create_document(
                arguments.get("doctype"),
                arguments.get("data")
            )
        
        elif name == "update_generic_document":
            return await handle_update_document(
                arguments.get("doctype"),
                arguments.get("name"),
                arguments.get("data")
            )
        
        elif name == "get_doctype_schema":
            doctype = arguments.get("doctype")
            if not doctype:
                return CallToolResult(
                    content=[TextContent(type="text", text="❌ DocType parameter required")],
                    isError=True
                )
            
            schema = await erpnext_client.get_doctype_meta(doctype)
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Schema for {doctype}:\n{json.dumps(schema, indent=2)}"
                )]
            )
        
        else:
            return await handle_dynamic_tool(name, arguments)
    
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Error: {str(e)}")],
            isError=True
        )


async def handle_get_document(doctype: str, name: str) -> CallToolResult:
    if not doctype or not name:
        return CallToolResult(
            content=[TextContent(type="text", text="❌ Both doctype and name are required")],
            isError=True
        )
    
    allowed, reason = permission_manager.validate_operation('read', doctype)
    if not allowed:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {reason}")],
            isError=True
        )
    
    result = await erpnext_client.get_doctype_doc(doctype, name)
    
    if result.get('data'):
        filtered_data = permission_manager.filter_allowed_fields(result['data'], doctype)
        result['data'] = filtered_data
    
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"{doctype} document '{name}':\n{json.dumps(result, indent=2)}"
        )]
    )


async def handle_list_documents(doctype: str, filters: Optional[Dict], 
                               fields: Optional[List[str]], limit: int) -> CallToolResult:
    """Handle list documents operation"""
    if not doctype:
        return CallToolResult(
            content=[TextContent(type="text", text="❌ DocType parameter required")],
            isError=True
        )
    
    allowed, reason = permission_manager.validate_operation('read', doctype)
    if not allowed:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {reason}")],
            isError=True
        )
    
    # Filter fields based on permissions
    if fields:
        allowed_fields = permission_manager.get_allowed_fields(doctype)
        fields = [f for f in fields if f in allowed_fields]
    
    result = await erpnext_client.get_doctype_list(doctype, filters, fields, limit)
    
    # Filter data based on permissions
    if result.get('data'):
        filtered_data = []
        for item in result['data']:
            filtered_item = permission_manager.filter_allowed_fields(item, doctype)
            filtered_data.append(filtered_item)
        result['data'] = filtered_data
    
    count = len(result.get('data', []))
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"Found {count} {doctype} documents:\n{json.dumps(result, indent=2)}"
        )]
    )


async def handle_create_document(doctype: str, data: Dict) -> CallToolResult:
    """Handle create document operation"""
    if not doctype or not data:
        return CallToolResult(
            content=[TextContent(type="text", text="❌ Both doctype and data are required")],
            isError=True
        )
    
    # Validate permissions and conditions
    allowed, reason = permission_manager.validate_operation('create', doctype, data)
    if not allowed:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {reason}")],
            isError=True
        )
    
    # Filter allowed fields
    filtered_data = permission_manager.filter_allowed_fields(data, doctype)
    
    result = await erpnext_client.create_doctype_doc(doctype, filtered_data)
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"✅ {doctype} document created successfully:\n{json.dumps(result, indent=2)}"
        )]
    )


async def handle_update_document(doctype: str, name: str, data: Dict) -> CallToolResult:
    """Handle update document operation"""
    if not doctype or not name or not data:
        return CallToolResult(
            content=[TextContent(type="text", text="❌ DocType, name, and data are all required")],
            isError=True
        )
    
    # Validate permissions and conditions
    allowed, reason = permission_manager.validate_operation('update', doctype, data, name)
    if not allowed:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ {reason}")],
            isError=True
        )
    
    # Filter allowed fields
    filtered_data = permission_manager.filter_allowed_fields(data, doctype)
    
    result = await erpnext_client.update_doctype_doc(doctype, name, filtered_data)
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"✅ {doctype} document '{name}' updated successfully:\n{json.dumps(result, indent=2)}"
        )]
    )


async def handle_dynamic_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle dynamically generated doctype-specific tools"""
    
    # Parse tool name to extract doctype and operation
    parts = name.split('_')
    if len(parts) < 3:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Invalid tool name: {name}")],
            isError=True
        )
    
    operation = parts[0]  # list, get, create, update, delete, search
    doctype_parts = parts[1:-1]  # middle parts form the doctype
    
    # Reconstruct doctype (handle spaces)
    doctype = ' '.join(word.capitalize() for word in doctype_parts)
    
    # Handle different operations
    if operation == "list" and parts[-1] == "documents":
        return await handle_list_documents(
            doctype,
            arguments.get("filters"),
            arguments.get("fields"),
            arguments.get("limit", 20)
        )
    
    elif operation == "get" and parts[-1] == "document":
        return await handle_get_document(doctype, arguments.get("name"))
    
    elif operation == "search" and parts[-1] == "documents":
        search_term = arguments.get("search_term")
        limit = arguments.get("limit", 10)
        
        if not search_term:
            return CallToolResult(
                content=[TextContent(type="text", text="❌ Search term required")],
                isError=True
            )
        
        result = await erpnext_client.search_doctypes(doctype, search_term, limit)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Search results for '{search_term}' in {doctype}:\n{json.dumps(result, indent=2)}"
            )]
        )
    
    elif operation == "create" and parts[-1] == "document":
        return await handle_create_document(doctype, arguments.get("data"))
    
    elif operation == "update" and parts[-1] == "document":
        return await handle_update_document(
            doctype,
            arguments.get("name"),
            arguments.get("data")
        )
    
    elif operation == "delete" and parts[-1] == "document":
        name = arguments.get("name")
        confirm = arguments.get("confirm", False)
        
        if not name or not confirm:
            return CallToolResult(
                content=[TextContent(type="text", text="❌ Document name and confirmation required for deletion")],
                isError=True
            )
        
        # Validate permissions
        allowed, reason = permission_manager.validate_operation('delete', doctype, document_name=name)
        if not allowed:
            return CallToolResult(
                content=[TextContent(type="text", text=f"❌ {reason}")],
                isError=True
            )
        
        result = await erpnext_client.delete_doctype_doc(doctype, name)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"✅ {doctype} document '{name}' deleted successfully:\n{json.dumps(result, indent=2)}"
            )]
        )
    
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Unknown tool: {name}")],
            isError=True
        )


async def main():
    """Main entry point for the enhanced MCP server"""
    import sys
    import traceback
    
    try:
        print("Starting Enhanced ERPNext MCP Server...")
        print(f"Config loaded from: {config_path}")
        
        print("Testing ERPNext connection...")
        connected = await erpnext_client.test_connection()
        if connected:
            print("ERPNext connection successful")
        else:
            print("ERPNext connection failed, but server will start anyway")
        
        doctypes = permission_manager.get_all_doctypes()
        print(f"Configured doctypes: {', '.join(doctypes)}")
        
        print("Server ready and waiting for connections...")
        
        async with stdio_server() as (read_stream, write_stream):
            try:
                if HAS_NOTIFICATION_OPTIONS:
                    notification_options = NotificationOptions()
                    capabilities = app.get_capabilities(
                        notification_options=notification_options,
                        experimental_capabilities={}
                    )
                else:
                    capabilities = app.get_capabilities()
            except TypeError:
                capabilities = app.get_capabilities()
            
            await app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="erpnext-mcp-server",
                    server_version="2.0.0",
                    capabilities=capabilities,
                ),
            )
            
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        print("Full traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Goodbye!")
    except Exception as e:
        print(f"Failed to start server: {e}")
        import traceback
        traceback.print_exc()