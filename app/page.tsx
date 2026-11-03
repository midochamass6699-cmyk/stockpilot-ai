
export default function Home() {
  const stocks = [
    { symbol: "NVDA", name: "NVIDIA", market: "NASDAQ" },
    { symbol: "SHOP", name: "Shopify", market: "TSX" },
    { symbol: "AMD", name: "Advanced Micro Devices", market: "NASDAQ" },
    { symbol: "PLTR", name: "Palantir", market: "NASDAQ" },
    { symbol: "RY", name: "Royal Bank", market: "TSX" }
  ];

  return (
    <main className="min-h-screen bg-[#090f1d] text-white p-6 md:p-12">
      <div className="max-w-5xl mx-auto">

        <header className="flex justify-between items-center mb-20">
          <h1 className="text-2xl font-bold text-green-400">
            STOCKPILOT AI
          </h1>
          <span className="text-green-400 text-sm">
            AI STOCK SCANNER
          </span>
        </header>

        <section className="mb-16">
          <p className="text-green-400 mb-4">
            SMARTER DAILY STOCK RESEARCH
          </p>

          <h2 className="text-5xl md:text-7xl font-bold mb-6">
            Find your next
            <span className="text-green-400"> trading opportunity.</span>
          </h2>

          <p className="text-slate-400 text-lg max-w-xl">
            AI-powered daily stock research for US and
            Canadian markets. Five carefully ranked
            trading candidates every morning.
          </p>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="text-2xl font-bold">
                Daily Top 5
              </h3>
              <p className="text-slate-400 text-sm mt-2">
                Sample watchlist — not live recommendations
              </p>
            </div>
            <span className="text-green-400 text-sm">
              US + CANADA
            </span>
          </div>

          <div className="space-y-3">
            {stocks.map((stock, index) => (
              <div
                key={stock.symbol}
                className="flex justify-between items-center
                bg-slate-800 p-5 rounded-xl"
              >
                <div className="flex gap-4 items-center">
                  <span className="text-slate-500">
                    0{index + 1}
                  </span>
                  <div>
                    <h4 className="font-bold text-lg">
                      {stock.symbol}
                    </h4>
                    <p className="text-slate-400 text-sm">
                      {stock.name}
                    </p>
                  </div>
                </div>

                <span className="text-green-400 text-sm">
                  {stock.market}
                </span>
              </div>
            ))}
          </div>
        </section>

        <footer className="text-center text-slate-500 text-sm mt-16">
          StockPilot AI © 2026 · Market research only.
          Trading involves risk.
        </footer>

      </div>
    </main>
  );
}

