#!/bin/bash
# Example demonstrating --tool-postfix usage

echo "Example 1: Default postfix (inferred from service)"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc"
echo "Tools will have names like: create_entity_for_Northwind, get_entity_for_Northwind, etc."
echo

echo "Example 2: Custom postfix"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --tool-postfix _nw"
echo "Tools will have names like: create_entity_nw, get_entity_nw, etc."
echo

echo "Example 3: With tool shrinking and custom postfix"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --tool-shrink --tool-postfix _nw"
echo "Tools will have shortened names like: crt_Categories_nw, get_Products_nw, etc."
echo

echo "Example 4: No postfix (use prefix instead)"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --no-postfix"
echo "Tools will have names like: Northwind_create_entity, Northwind_get_entity, etc."