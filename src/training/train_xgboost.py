"""Train on the training split and compare strategies on validation only."""

from src.backtesting.run_backtest import command

main = command(train_model=True)

if __name__ == "__main__":
    main()
