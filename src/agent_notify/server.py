from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="agent-notify")

def main():
    mcp.run()

if __name__ == "__main__":
    main()
