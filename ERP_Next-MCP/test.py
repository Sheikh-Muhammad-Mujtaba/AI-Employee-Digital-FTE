import asyncio
import json
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

async def run_interactive():
    # Load config
    config_path = "config/multi_doctype_config.json"
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    from src.erpnext_client import ERPNextClient
    from src.permissions import PermissionManager
    
    # Initialize clients
    erp_config = config["erpnext"]
    client = ERPNextClient(
        url=erp_config["url"],
        api_key=erp_config["api_key"],
        api_secret=erp_config["api_secret"]
    )
    perm_manager = PermissionManager(config)
    
    # Test connection
    print("\n🔗 Testing connection...")
    connected = await client.test_connection()
    print(f"Connected: {connected}")
    if not connected:
        print("❌ Cannot connect to ERPNext. Exiting.")
        return
    
    # Menu for user
    print("\n📌 Choose operation:")
    print("1. Get Item")
    print("2. Create Item")
    print("3. Update Item")
    print("4. Delete Item")
    
    choice = input("Enter choice (1-4): ").strip()
    
    try:
        if choice == "1":  # GET
            item_code = input("Enter Item Code to fetch: ").strip()
            result = await client.get_item(item_code)
            print("\n📄 Item Data:")
            print(json.dumps(result, indent=2))
        
        elif choice == "2":  # CREATE
            item_code = input("Enter new Item Code: ").strip()
            item_name = input("Enter Item Name: ").strip()
            uom = input("Enter Stock UOM (default Nos): ").strip() or "Nos"
            group = input("Enter Item Group (default All Item Groups): ").strip() or "All Item Groups"
            
            test_data = {
                "item_code": item_code,
                "item_name": item_name,
                "is_stock_item": 1,
                "stock_uom": uom,
                "item_group": group,
            }
            
            filtered = perm_manager.filter_allowed_fields(test_data, "Item")
            result = await client.create_item(filtered)
            print("\n✅ Item Created:")
            print(json.dumps(result, indent=2))
        
        elif choice == "3":  # UPDATE
            item_code = input("Enter Item Code to update: ").strip()
            field = input("Enter field to update (e.g. item_name): ").strip()
            value = input(f"Enter new value for {field}: ").strip()
            
            update_data = {field: value}
            filtered = perm_manager.filter_allowed_fields(update_data, "Item")
            result = await client.update_item(item_code, filtered)
            print("\n✅ Item Updated:")
            print(json.dumps(result, indent=2))
        
        elif choice == "4":  # DELETE
            item_code = input("Enter Item Code to delete: ").strip()
            confirm = input(f"⚠️ Are you sure you want to delete {item_code}? (yes/no): ").strip().lower()
            
            if confirm == "yes":
                result = await client.delete_item(item_code)
                print("\n✅ Item Deleted:")
                print(json.dumps(result, indent=2))
            else:
                print("❌ Delete cancelled")
        
        else:
            print("❌ Invalid choice")
    
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n✅ TEST COMPLETED!")

if __name__ == "__main__":
    asyncio.run(run_interactive())
