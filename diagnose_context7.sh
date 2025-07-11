#!/bin/bash

echo "=== Context7 MCP Diagnostic Script ==="
echo

# Check Node.js and npm versions
echo "1. Checking Node.js and npm versions:"
node --version
npm --version
npx --version
echo

# Check if the package can be found
echo "2. Checking if @upstash/context7-mcp package exists:"
npm view @upstash/context7-mcp version 2>/dev/null || echo "Package not found in registry"
echo

# Try to run with explicit stdio mode
echo "3. Testing Context7 MCP server startup (will timeout after 5 seconds):"
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-15","capabilities":{"roots":{"listChanged":true},"sampling":{}}},"id":1}' | npx -y @upstash/context7-mcp 2>&1 &
PID=$!
sleep 5
kill $PID 2>/dev/null
echo

# Check for any npm cache issues
echo "4. Checking npm cache:"
npm cache verify
echo

# Try alternative installation method
echo "5. Testing direct execution with debugging:"
export DEBUG=*
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-15","capabilities":{"roots":{"listChanged":true},"sampling":{}}},"id":1}' | npx -y @upstash/context7-mcp 2>&1 | head -50 &
PID=$!
sleep 3
kill $PID 2>/dev/null
echo

echo "=== Diagnostic Complete ==="
echo
echo "Potential issues to check:"
echo "1. The Context7 MCP server might be waiting for stdin input in JSON-RPC format"
echo "2. There might be network connectivity issues downloading the package"
echo "3. The server might be starting but not providing visible output"
echo "4. Try running Claude Code with --verbose flag for more details"