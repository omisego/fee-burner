defmodule OMG.Burner.State do

  use GenServer

  # API
  def start_link(initial_state \\ {%{}, %{}}) do
    GenServer.start_link(__MODULE__, initial_state, name: __MODULE__)
  end

  @spec add_fee(OMG.Burner.token, integer) :: :ok
  def add_fee(token, value) when is_atom(token) and is_integer(value) do
    GenServer.cast(__MODULE__, {:add_fee, token, value})
    :ok
  end

  @spec move_to_pending(OMG.Burner.token) :: {:ok, pos_integer} | OMG.Burner.error
  def move_to_pending(token) when is_atom(token) do
    GenServer.call(__MODULE__, {:move_to_pending, token})
  end

  @spec confirm_pending(OMG.Burner.token) :: :ok | OMG.Burner.error
  def confirm_pending(token) when is_atom(token) do
    GenServer.call(__MODULE__, {:confirm_pending, token})
  end

  @spec cancel_exit(OMG.Burner.token) :: :ok | OMG.Burner.error
  def cancel_exit(token) when is_atom(token) do
    GenServer.call(__MODULE__, {:cancel_exit, token})
  end

  @spec get_pending_fees(OMG.Burner.token) :: {:ok, pos_integer, OMG.Burner.tx_hash}
  def get_pending_fees(token) when is_atom(token) do
    GenServer.call(__MODULE__, {:get_preexited, token})
  end

  @spec get_pending_fees() :: list({atom, pos_integer, OMG.Burner.tx_hash})
  def get_pending_fees() do
    GenServer.call(__MODULE__, :get_pending)
  end

  @spec get_accumulated_fees(OMG.Burner.token) :: {:ok, pos_integer} | OMG.Burner.error
  def get_accumulated_fees(token) when is_atom(token) do
    GenServer.call(__MODULE__, {:get_accumulated, token})
  end

  @spec get_accumualted_fees() :: list({atom, pos_integer})
  def get_accumualted_fees() do
    GenServer.call(__MODULE__, :get_accumulated)
  end

  # GenServer

  def init({_accumulated, _preexited} = state) do
    {:ok, state}
  end

  def handle_cast({:add_fee, token, value}, {accumulated, pending}) do
    updated_accumulated = do_add_fee(token, value, accumulated)
    {:noreply, {updated_accumulated, pending}}
  end

  def handle_call({:move_to_pending, token}, _from, state) do
    {reply, new_state} = do_move_to_pending(token, state)
    {:reply, reply, new_state}
  end

  def handle_call({:get_accumulated, token}, _from, {accumulated, _} = state) do
    {:reply, Map.fetch(accumulated, token), state}
  end

  def handle_call(:get_accumulated, _from, {accumulated, _} = state) do

    {:reply, Map.to_list(accumulated), state}
  end

  def handle_call({:get_pending, token}, _from, {_, pending} = state) do
    reply =
      case Map.fetch(pending, token) do
        {:ok, map} -> {:ok, map_pending({token, map})}
        {:error, reason} -> {:error, reason}
      end
    {:reply, reply, state}
  end

  def handle_call(:get_pending, _from, {_, pending} = state) do
    reply = pending
            |> Map.to_list()
            |> Enum.map(&map_pending/1)

    {:reply, reply, state}
  end

  def handle_call({:confirm_pending, token}, _from, {accumulated, pending}) do
    {reply, updated_pending} = do_confirm_exit(token, pending)
    {:reply, reply, {accumulated, updated_pending}}
  end

  def handle_call({:cancel_exit, token}, _from, state) do
    {reply, new_state} = do_cancel_exit(token, state)
    {:reply, reply, new_state}
  end

  defp do_add_fee(token, value, accumulated) do
    accumulated
    |> Map.update(token, value, &(&1 + value))
    |> Enum.filter(fn {_token, value} -> value > 0 end)
    |> Map.new
  end

  defp do_move_to_pending(token, {accumulated, pending} = state) do
    with :error <- Map.fetch(pending, token),
         {:ok, value} <- Map.fetch(accumulated, token) do

      updated_state = move_to_pending(token, state)
      {{:ok, value}, updated_state}

    else
      {:ok, _} -> {{:error, :exit_already_started}, state}
      _ -> {{:error, :nothing_to_exit}, state}
    end
  end

  defp move_to_pending(token, {accumulated, pending}) do
    {value, updated_accumulated} = Map.pop(accumulated, token)
    updated_pending = Map.put_new(pending, token, %{value: value})
    {updated_accumulated, updated_pending}
  end

  defp do_confirm_exit(token, pending) do
    case Map.fetch(pending, token) do
      {:ok, _} -> {:ok, Map.delete(pending, token)}
      _ -> {{:error, :nothing_to_confirm}, pending}
    end
  end

  defp do_cancel_exit(token, {accumulated, pending} = state) do
    case Map.fetch(pending, token) do
      {:ok, value} -> {:ok, {do_add_fee(token, value, accumulated), Map.delete(pending, token)}}
      _ -> {{:error, :nothing_to_cancel}, state}
    end
  end

  defp map_pending({token, %{value: value, tx_hash: tx_hash}})do
    {token, value, tx_hash}
  end

  defp map_pending({token, %{value: value}}) do
    {token, value, nil}
  end

end