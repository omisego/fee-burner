defmodule OMG.Burner.Eth do
  @moduledoc """
     This module is an interface to the Ethereum world. It is responsible for sending start exit transaction.
     Whenever a transaction is sent it waits till the transaction has been mined and informs the system about the confirmation.
  """

  require Logger

  use AdjustableServer
  alias OMG.Eth

  @success "0x1"
  @failure "0x0"

  def start_link(args \\ %{}) do
    GenServer.start_link(__MODULE__, args, name: __MODULE__)
  end

  def init(args) do
    refresh_period = Map.get(args, :refresh_period) || Application.get_env(:omg_burner, :short_period)
    max_checks = Map.get(args, :max_checks) || Application.get_env(:omg_burner, :max_checks)
    authority = Map.get(args, :authority) || Application.get_env(:omg_burner, :authority)
    contract = Map.get(args, :contract) || Application.get_env(:omg_burner, :contract)

    state = %{
      max_checks: max_checks,
      refresh_period: refresh_period,
      contract: contract,
      authority: authority
    }

    {:ok, state}
  end

  def start_fee_exit(token, value, %{gas_price: _} = opts) when is_atom(token) do
    GenServer.call(__MODULE__, {:start, token, value, opts})
  end

  def handle_call({:start, token, value, opts}, _from, state) do
    contract = Map.get(opts, :contract) || Map.fetch!(state, :contract)
    authority = Map.get(opts, :from) || Map.fetch!(state, :authority)
    gas_price = Map.fetch!(opts, :gas_price)

    refresh_period = Map.fetch!(state, :refresh_period)

    token_address =
      Application.get_env(:omg_burner, :thresholds)
      |> Map.fetch!(token)
      |> Map.fetch!(:address)

    IO.puts(inspect(%{contract: contract, authority: authority, gas_price: gas_price}))

    {:ok, tx_hash} = Eth.RootChain.start_fee_exit(token_address, value, gas_price, authority, contract)
    Process.send_after(self(), {:wait, tx_hash, token, 0}, refresh_period)

    {:reply, {:ok, tx_hash}, state}
  end

  def handle_info({:wait, tx_hash, token, count}, state) do
    max_count = Map.get(state, :max_checks)
    refresh_period = Map.get(state, :refresh_period)
    do_handle_wait(tx_hash, token, count, max_count, refresh_period)
    {:noreply, state}
  end

  defp do_handle_wait(_, token, count, max_count, _) when count > max_count,
    do: OMG.Burner.cancel_pending_exit_start(token)

  defp do_handle_wait(tx_hash, token, count, _, refresh_period) do
    case Ethereumex.HttpClient.eth_get_transaction_receipt(tx_hash) do
      {:ok, receipt} when receipt != nil -> process_receipt(receipt, token)
      _ -> Process.send_after(self(), {:wait, tx_hash, token, count + 1}, refresh_period)
    end

    :ok
  end

  defp process_receipt(%{"status" => status}, token) when status == @success,
    do: OMG.Burner.confirm_pending_exit_start(token)

  defp process_receipt(%{"status" => status}, token) when status == @failure,
    do: OMG.Burner.cancel_pending_exit_start(token)
end
