#!/bin/bash
# Examples of using the --entities parameter

echo "Example 1: Generate tools for all entities (default behavior)"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc"
echo

echo "Example 2: Generate tools only for Products and Categories"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --entities 'Products,Categories'"
echo

echo "Example 3: Generate tools for a single entity"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --entities 'Orders'"
echo

echo "Example 4: With verbose output to see filtering messages"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --entities 'Products,Orders' --verbose"
echo

echo "Example 5: Combine with other options"
echo "python odata_mcp.py --service https://services.odata.org/V4/Northwind/Northwind.svc --entities 'Products,Categories' --tool-shrink --tool-postfix '_nw'"