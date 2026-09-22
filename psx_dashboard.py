import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QInputDialog
)


class PSXDashboard(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PSX Elite Scanner")
        self.resize(1200, 700)

        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
            }

            QPushButton {
                min-height: 45px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)

        main_layout = QHBoxLayout()

        # =====================
        # LEFT PANEL
        # =====================

        left = QVBoxLayout()

        title = QLabel("🚀 PSX ELITE SCANNER")
        title.setStyleSheet("""
            font-size: 20pt;
            font-weight: bold;
            color: darkblue;
            padding: 10px;
        """)
        left.addWidget(title)

        left.addWidget(QLabel("Market Status : BULLISH"))
        left.addWidget(QLabel("Buy Signals : 18"))
        left.addWidget(QLabel("Watch Signals : 32"))
        left.addWidget(QLabel("Sell Signals : 14"))

        left.addWidget(QLabel(""))
        left.addWidget(QLabel("TOP 10 OPPORTUNITIES"))

        stocks = [
            "🟢 PRL - STRONG BUY",
            "🟢 ATRL - STRONG BUY",
            "🟢 OGDC - STRONG BUY",
            "🟩 AKBL - BUY",
            "🟦 NETSOL - OPPORTUNITY",
            "🟦 SYS - OPPORTUNITY",
            "🟨 HUBC - HOLD",
            "🟧 PPL - SELL",
            "🔴 GTYR - STRONG SELL",
            "🔴 AGHA - STRONG SELL"
        ]

        for stock in stocks:

            btn = QPushButton(stock)

            if "STRONG BUY" in stock:
                btn.setStyleSheet(
                    "background-color:#00aa00;color:white;font-weight:bold;"
                )

            elif "BUY" in stock:
                btn.setStyleSheet(
                    "background-color:#44cc44;color:black;font-weight:bold;"
                )

            elif "OPPORTUNITY" in stock:
                btn.setStyleSheet(
                    "background-color:#3399ff;color:white;font-weight:bold;"
                )

            elif "HOLD" in stock:
                btn.setStyleSheet(
                    "background-color:#ffff66;color:black;font-weight:bold;"
                )

            elif "SELL" in stock:
                btn.setStyleSheet(
                    "background-color:#ff9933;color:black;font-weight:bold;"
                )

            left.addWidget(btn)

        # =====================
        # RIGHT PANEL
        # =====================

        right = QVBoxLayout()

        right.addWidget(QLabel("PORTFOLIO SUMMARY"))
        right.addWidget(QLabel("---------------------------"))
        right.addWidget(QLabel("Investment : 942,135"))
        right.addWidget(QLabel("Current Value : 888,476"))
        right.addWidget(QLabel("Return : -5.7%"))
        right.addWidget(QLabel("Winning : 1"))
        right.addWidget(QLabel("Losing : 4"))
        right.addWidget(QLabel("Best : SYS +2.63%"))
        right.addWidget(QLabel("Worst : GTYR -16.72%"))

        right.addWidget(QLabel(""))

        right.addWidget(QLabel("MARKET HEALTH"))
        right.addWidget(QLabel("---------------------------"))
        right.addWidget(QLabel("Trend : BULLISH"))
        right.addWidget(QLabel("Risk : LOW"))
        right.addWidget(QLabel("Accumulation : 10"))
        right.addWidget(QLabel("Distribution : 9"))

        right.addWidget(QLabel(""))
        right.addWidget(QLabel("QUICK ACTIONS"))

        btn_search = QPushButton("SEARCH STOCK")
        btn_search.clicked.connect(self.search_stock)
        right.addWidget(btn_search)

        btn_short = QPushButton("SHORT TERM PICKS")
        btn_short.clicked.connect(self.short_term)
        right.addWidget(btn_short)

        btn_long = QPushButton("LONG TERM PICKS")
        btn_long.clicked.connect(self.long_term)
        right.addWidget(btn_long)

        btn_opportunity = QPushButton("OPPORTUNITY SCANNER")
        btn_opportunity.clicked.connect(self.opportunity_scanner)
        right.addWidget(btn_opportunity)

        btn_watch = QPushButton("WATCHLIST")
        btn_watch.clicked.connect(self.watchlist)
        right.addWidget(btn_watch)

        btn_money = QPushButton("SMART MONEY")
        btn_money.clicked.connect(self.smart_money)
        right.addWidget(btn_money)

        btn_portfolio = QPushButton("PORTFOLIO")
        btn_portfolio.clicked.connect(self.portfolio)
        right.addWidget(btn_portfolio)

        btn_refresh = QPushButton("REFRESH")
        btn_refresh.clicked.connect(self.refresh_data)
        right.addWidget(btn_refresh)

        main_layout.addLayout(left, 2)
        main_layout.addLayout(right, 1)

        self.setLayout(main_layout)

    # =====================
    # FUNCTIONS
    # =====================

    def search_stock(self):

        symbol, ok = QInputDialog.getText(
            self,
            "Search Stock",
            "Enter Symbol:"
        )

        if ok and symbol:

            QMessageBox.information(
                self,
                "Stock Analysis",
                f"{symbol.upper()}\n\n"
                f"Signal : STRONG BUY\n"
                f"Entry : ENTRY NOW\n"
                f"RSI : 58\n"
                f"Target 1 : 346\n"
                f"Target 2 : 357"
            )

    def short_term(self):

        QMessageBox.information(
            self,
            "Short Term Picks",
            "PRL\nATRL\nAKBL\nOGDC\nILP"
        )

    def long_term(self):

        QMessageBox.information(
            self,
            "Long Term Picks",
            "OGDC\nMARI\nFFC\nENGRO\nHUBC"
        )

    def opportunity_scanner(self):

        QMessageBox.information(
            self,
            "Opportunity Scanner",
            "EARLY ACCUMULATION\n\n"
            "OGDC\n"
            "AKBL\n"
            "NETSOL\n"
            "SYS\n"
            "POL\n\n"
            "WATCH CLOSELY\n\n"
            "Accumulation detected.\n"
            "Breakout not confirmed."
        )

    def watchlist(self):

        QMessageBox.information(
            self,
            "Watchlist",
            "PRL\nATRL\nOGDC\nAKBL\nNETSOL"
        )

    def smart_money(self):

        QMessageBox.information(
            self,
            "Smart Money",
            "Accumulation:\n\nPRL\nATRL\nOGDC"
        )

    def portfolio(self):

        QMessageBox.information(
            self,
            "Portfolio",
            "Investment : 942,135\n"
            "Current Value : 888,476\n"
            "Return : -5.7%"
        )

    def refresh_data(self):

        QMessageBox.information(
            self,
            "Refresh",
            "Scanner Updated Successfully"
        )


app = QApplication(sys.argv)

window = PSXDashboard()
window.show()

sys.exit(app.exec())