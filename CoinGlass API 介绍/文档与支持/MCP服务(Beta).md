> ## Documentation Index
> Fetch the complete documentation index at: https://docs.coinglass.com/llms.txt
> Use this file to discover all available pages before exploring further.

# 🧩 CoinGlass MCP (Beta)

Once connected to CoinGlass MCP, your AI model or agent can directly query CoinGlass data and generate analytical results.

# What Can AI Do with CoinGlass MCP?

With CoinGlass MCP, AI Agents can:

**Analyze Derivatives Markets**

* Query funding rate trends
* Monitor open interest changes
* Analyze liquidation distributions

**Identify Market Sentiment**

* Track long vs short positioning
* Detect market overheating or panic

**Track Capital Flows**

* View ETF inflows and outflows
* Monitor exchange position changes

**Generate Market Reports**

* Automatically summarize market trends
* Generate daily market analysis

**Build Automated Agents**

* Build market monitoring bots
* Build trading signal systems

With MCP, AI can directly understand the CoinGlass API without requiring developers to manually read complex API documentation.

# Quick Start (Beginner Guide)

CoinGlass MCP Server Endpoint

```

https://api-mcp.coinglass.com/mcp

```

To execute API requests, you need to provide your CoinGlass API Key in the MCP configuration.

# MCP Configuration

<Tabs>
  <Tab title="Cursor">
    **Step 1: Install and Open Cursor**

    If you have not installed Cursor, visit:

    ```
    https://cursor.sh
    ```

    Download and install Cursor, then launch the application.

    **Step 2: Create MCP Configuration File**

    Cursor automatically reads a configuration file named `mcp.json`.

    It is recommended to create the following file in your project directory:

    ```
    .cursor/mcp.json
    ```

    Example project structure:

    ```
    your-project
    ├── .cursor
    │   └── mcp.json
    ├── src
    └── README.md
    ```

    You can also use a global configuration (applies to all Cursor projects):

    ```
    ~/.cursor/mcp.json
    ```

    **Step 3: Add CoinGlass MCP Configuration**

    Add the following content to `mcp.json`:

    ```json
    {
      "mcpServers": {
        "coinglass-api": {
          "url": "https://api-mcp.coinglass.com/mcp",
          "headers": {
            "CG-API-KEY": "YOUR_API_KEY"
          }
        }
      }
    }
    ```

    Replace `YOUR_API_KEY` with your CoinGlass API Key.

    **Step 4: Restart Cursor**

    Save the file, then close and reopen Cursor.\
    Cursor will automatically load the MCP configuration.
  </Tab>

  <Tab title="Windsurf">
    **Step 1: Install Windsurf**

    If you have not installed Windsurf, visit:

    ```
    https://windsurf.com
    ```

    Download and install Windsurf.

    **Step 2: Locate MCP Configuration File**

    Windsurf uses the following configuration file:

    ```
    ~/.codeium/windsurf/mcp_config.json
    ```

    If the file does not exist, you can create it manually.

    **Step 3: Add CoinGlass MCP Configuration**

    Add the following content to `mcp_config.json`:

    ```json
    {
      "mcpServers": {
        "coinglass-api": {
          "url": "https://api-mcp.coinglass.com/mcp",
          "headers": {
            "CG-API-KEY": "YOUR_API_KEY"
          }
        }
      }
    }
    ```

    Replace `YOUR_API_KEY` with your CoinGlass API Key.

    **Step 4: Restart Windsurf**

    Save the configuration file and restart Windsurf to apply the changes.
  </Tab>

  <Tab title="Claude Desktop">
    **Step 1: Install Claude Desktop**

    If you have not installed Claude Desktop, visit:

    ```
    https://claude.ai/download
    ```

    Download and install Claude Desktop.

    **Step 2: Locate Configuration File**

    Claude Desktop uses the following configuration file:

    Mac:

    ```
    ~/Library/Application Support/Claude/claude_desktop_config.json
    ```

    Windows:

    ```
    %APPDATA%\Claude\claude_desktop_config.json
    ```

    If the file does not exist, you can create it manually.

    **Step 3: Add CoinGlass MCP Configuration**

    Edit `claude_desktop_config.json` and add the following:

    ```json
    {
      "mcpServers": {
        "coinglass-api": {
          "url": "https://api-mcp.coinglass.com/mcp",
          "headers": {
            "CG-API-KEY": "YOUR_API_KEY"
          }
        }
      }
    }
    ```

    Replace `YOUR_API_KEY` with your CoinGlass API Key.

    **Step 4: Restart Claude Desktop**

    Save the file, then close and reopen Claude Desktop for the configuration to take effect.
  </Tab>
</Tabs>

***

## Supported MCP Clients

CoinGlass MCP can be used with various AI tools, including:

* Claude Desktop
* Cursor
* Windsurf
* VSCode
* Claude Code CLI
* Open Code CLI
* Google Gemini CLI
* MCP Inspector
* Cline
* OpenClaw (via MCPorter)

We recommend using **Cursor or Claude Desktop** for the best experience.

***

# Test MCP Connection

After completing the configuration:

1. Open your AI client (Cursor, Claude, Windsurf)
2. Start a new AI chat
3. Enter a CoinGlass query

# Example Queries (Prompt Examples)

You can directly use natural language queries in your AI client.

**Liquidation Analysis**

```
Get the BTC liquidation heatmap for the past 7 days and analyze potential liquidation zones.
```

**Funding Rate Trend**

```
Check the BTC funding rate trend over the past 7 days. Is the market currently bullish or bearish?
```

**Exchange Comparison**

```
Compare the current ETH open interest between Binance and OKX.
```

**Order Book**

```
Analyze the current BTC order book depth. Where are the main bid and ask clusters? Are there clear support and resistance levels?
```

**ETF Flows**

```
Is BTC ETF capital flowing in or out today?
```

**Liquidation Stats**

```
Which cryptocurrency had the highest liquidations across the market in the past 24 hours?
```

**Market Summary**

```
Generate a market summary based on current open interest, funding rates, and fear & greed index.
```

<br />

***

<br />

# Available MCP Tools

CoinGlass MCP Server currently provides more than 30 tools, for example:

### get\_futures\_liquidation\_exchange\_list

List the futures liquidation data by exchange.

### get\_bitcoin\_etf\_flow\_history

Get the historical inflow and outflow of Bitcoin ETFs.

### get\_futures\_aggregated\_open\_interest\_history

Get the aggregated open interest history of a cryptocurrency.

### get\_futures\_funding\_rate\_history

Get the historical futures funding rates.

***

# MCP vs REST API

Use **MCP** for:

* Agent automation: build agents that react to market data and trigger actions
* Trading monitoring: track liquidation events and market sentiment in real time
* Natural language queries: query data without writing API calls
* Market reports: generate daily summaries and insights automatically
* Deep research: analyze historical positioning and price divergence

Use **REST API** for:

* Backend services
* Automated scripts
* High-performance data requests
* Production systems

***

# Limitations & Known Issues

**Beta Status**

CoinGlass MCP Server is currently in Beta. Tool schemas may change as the API evolves.

**Rate Limits**

MCP requests are subject to your CoinGlass API Key quota.

We recommend using a higher-tier API plan for the best experience.

***

# Security Notes

Never expose your API Key in public repositories.

Always store your API keys securely and avoid committing configuration files containing sensitive information.

***