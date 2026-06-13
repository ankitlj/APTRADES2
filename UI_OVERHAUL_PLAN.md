# APTRADES2 UI Overhaul — Match APTRADES 100%

Goal: make APTRADES2's frontend visually identical to APTRADES (github.com/ankitlj/APTRADES)
— fonts, colors, tables, boxes, layouts, charts, dark/light mode, top-right theme ("A") menu,
and the dashboard market ticker (Nifty/BankNifty/Sensex scrolling right→left).

## Hard constraint — FROZEN, never edited
Data layer + trading/websocket logic must not change:
- `frontend/src/lib/api.ts`
- `frontend/src/lib/realtime.ts`
- `frontend/src/hooks/useLiveMarketData.tsx`
- `frontend/src/hooks/useQuotes.ts`
- entire `backend/`

Only JSX markup, className, CSS, and new presentational components change. Every page keeps
its existing data calls and socket subscriptions exactly as-is.

## Architecture gap
| | APTRADES2 (now) | APTRADES (target) |
|---|---|---|
| Styling | custom index.css | Tailwind v4 + shadcn/ui (Radix) |
| Theme | none | next-themes (dark/light + accent + analyzer/sandbox) |
| Icons | none | lucide-react |
| Charts | custom PayoffChart | lightweight-charts + plotly |
| Ticker | none | .market-ticker-track (30s scroll) |
| Layout | AppShell | Layout + Navbar + TopHeader + Footer + MobileBottomNav |

## Page map (APTRADES2 -> APTRADES look source)
- DashboardPage -> Dashboard
- OptionChainPage -> OptionChain
- PositionsPage -> Positions
- OrderbookPage -> OrderBook
- TradebookPage -> TradeBook
- ActionCentrePage -> ActionCenter
- LogsPage -> LogsIndex
- ToolsPage -> Tools
- OITrackerPage -> OITracker
- OIProfilePage -> OIProfile
- StrategyBuilderPage -> StrategyBuilder
- StrategyPortfolioPage -> StrategyPortfolio

## Steps (test + push + permission gate after each)
1. Audit & map (this doc). No code change.
2. Foundation: Tailwind v4 + shadcn/ui primitives + next-themes + lucide-react + theme tokens
   (oklch) + index.css; rebuild layout shell (Navbar/Sidebar + TopHeader with theme "A" menu +
   Footer + MobileBottomNav). Global look changes on every page.
3. Dashboard + market ticker (Nifty/BankNifty/Sensex right->left). Live hooks untouched.
4. Pages batch 1: OptionChain, Positions, Orderbook, Tradebook, OITracker, OIProfile.
5. Pages batch 2 + polish: ActionCentre, Logs, Tools, StrategyBuilder, StrategyPortfolio,
   descriptions, mobile/responsive pass.

Token discipline: reuse APTRADES's actual components/CSS verbatim where possible; work
strictly page-by-page; never re-read frozen files after Step 1.
