defmodule OMG.Burner.Fixtures do

  use ExUnitFixtures.FixtureModule
  import OMG.Burner.DevHelpers

  @gas_price 20_000_000_000

  deffixture geth do
    {:ok, exit_fn} = OMG.Eth.DevGeth.start()
    on_exit(exit_fn)
    :ok
  end

  deffixture ethereumex (geth) do
    {:ok, _} = Application.ensure_all_started(:ethereumex)
    :ok
  end

  deffixture authority(ethereumex) do
    :ok = ethereumex
    authority = create_unlock_and_fund_entity()
  end

  deffixture root_chain(authority) do
    burner_addr = "0x00"
    {:ok, contract, tx_hash} = create_root_chain("../../", authority, burner_addr)
    contract
  end

  deffixture environment(ethereumex) do
    :ok = ethereumex
    OMG.Burner.DevHelpers.prepare_env!("../../")
  end

  deffixture alice(ethereumex) do
    :ok = ethereumex
    OMG.Burner.DevHelpers.create_unlock_and_fund_entity()
  end

  deffixture tx_opts(authority, root_chain) do
    %{
      gas_price: @gas_price,
      from: authority,
      contract: root_chain
    }
  end

  deffixture gasstation_response do
    ~s({
    "average":29.0,
    "fastestWait":0.6,
    "fastWait":0.7,
    "fast":53.0,
    "safeLowWait":2.6,
    "blockNum":6275834,
    "avgWait":2.4,
    "block_time":15.737113402061855,
    "speed":0.8973564106105982,
    "fastest":400.0,
    "safeLow":28.0
    })
  end

  deffixture coinmarketcap_response do
    ~s({
        "data": {
            "id": 1,
            "name": "Bitcoin",
            "symbol": "BTC",
            "website_slug": "bitcoin",
            "rank": 1,
            "circulating_supply": 17250525.0,
            "total_supply": 17250525.0,
            "max_supply": 21000000.0,
            "quotes": {
                "USD": {
                    "price": 7032.1841007,
                    "volume_24h": 4973222636.60049,
                    "market_cap": 121308867634.0,
                    "percent_change_1h": -2.98,
                    "percent_change_24h": -3.91,
                    "percent_change_7d": -0.56
                },
                "EUR": {
                    "price": 6065.1814328287,
                    "volume_24h": 4289349818.618934,
                    "market_cap": 104627563937.0,
                    "percent_change_1h": -2.98,
                    "percent_change_24h": -3.91,
                    "percent_change_7d": -0.56
                }
            },
            "last_updated": 1536145822
        },
        "metadata": {
            "timestamp": 1536145348,
            "error": null
        }
    })

  end

end