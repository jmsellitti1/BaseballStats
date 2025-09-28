import statsapi  # pyright: ignore[reportMissingImports]
import pandas as pd
from tqdm import tqdm
import os
import pickle
import matplotlib.pyplot as plt

def update_cumulative(df, player, hr_dates):
    """Update cumulative home run counts for a player in the dataframe."""
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'])
    df_dates = df['Date']

    total = 0
    last_idx = 0
    for hr_date in hr_dates:
        matches = df_dates[df_dates == hr_date]
        if matches.empty:
            print(f"Warning: No match found for {hr_date} for player {player}")
            continue
        idx = matches.index[0]
        if idx - 1 >= last_idx:
            df.loc[last_idx:idx-1, player] = total
        total += 1
        df.loc[idx, player] = total
        last_idx = idx + 1
    if last_idx < len(df):
        df.loc[last_idx:, player] = total

def get_player_team_id(player_name):
    """Get the team ID for a given player name."""
    try:
        players = statsapi.lookup_player(player_name)
        if not players:
            print(f"Warning: Player '{player_name}' not found")
            return None
        
        return players[0]['currentTeam']['id']
    except Exception as e:
        print(f"Error getting team for {player_name}: {e}")
        return None

def get_home_run_dates(player_name, season):
    """Get all home run dates for a specific player within a date range."""
    team_id = get_player_team_id(player_name)
    if not team_id:
        return []
    
    try:
        schedule = statsapi.schedule(season=season, team=team_id)
        schedule = [game for game in schedule if game['game_type'] == 'R']
        hr_dates = []
        
        for game in tqdm(schedule, desc=f"Processing Games for {player_name}"):
            try:
                scoring_plays = statsapi.game_scoring_play_data(game['game_id'])
                for play in scoring_plays['plays']:
                    description = play['result']['description']
                    if description.startswith((f'{player_name} homers', f'{player_name} hits a grand slam')):
                        hr_dates.append(game['game_date'])
            except Exception as e:
                print(f"Error processing game {game['game_id']}: {e}")
                continue
                
        return hr_dates
    except Exception as e:
        print(f"Error getting schedule for {player_name}: {e}")
        return []

def create_cumulative_home_runs_graph(player_names, season):
    """
    Create a cumulative home runs comparison graph for multiple players.
    
    Args:
        player_names (list): List of player names to compare
        season (int): The year/season (e.g., 2025)
    
    Returns:
        pandas.DataFrame: The dataframe with cumulative home run data
    """
    
    data_folder = 'data'
    df_path = os.path.join(data_folder, f'HR_{season}.pkl')
    os.makedirs(data_folder, exist_ok=True)
    
    if os.path.exists(df_path):
        print("Loading existing DataFrame state...")
        with open(df_path, 'rb') as f:
            df = pickle.load(f)
        
        new_players = [player for player in player_names if player not in df.columns]
        if new_players:
            print(f"Adding new players: {new_players}")
            for player in new_players:
                df[player] = 0
                hr_dates = get_home_run_dates(player, season)
                update_cumulative(df, player, hr_dates)
            
            with open(df_path, 'wb') as f:
                pickle.dump(df, f)
            print(f"Updated DataFrame state saved to {df_path}")
    else:
        print("Creating new DataFrame...")
        schedule = statsapi.schedule(season=season, team=get_player_team_id(player_names[0]))
        schedule = [game for game in schedule if game['game_type'] == 'R']
        start_date = pd.to_datetime(schedule[0]['game_date'])
        end_date = pd.to_datetime(schedule[-1]['game_date'])
        dates = pd.date_range(start=start_date, end=end_date)
        df_data = {'Date': dates}
        
        for player in player_names:
            df_data[player] = 0
        
        df = pd.DataFrame(df_data)
        
        for player in player_names:
            print(f"Getting home run data for {player}...")
            hr_dates = get_home_run_dates(player, season)
            update_cumulative(df, player, hr_dates)
        
        with open(df_path, 'wb') as f:
            pickle.dump(df, f)
        print(f"DataFrame state saved to {df_path}")
    
    plt.figure(figsize=(12, 6))
    
    for player in player_names:
        if player in df.columns:
            plt.plot(df['Date'], df[player], label=player)
        else:
            print(f"Warning: {player} not found in dataframe")
    
    plt.xlabel('Date')
    plt.ylabel('Home Runs (Cumulative)')
    plt.title(f'Cumulative Home Runs: {" vs. ".join(player_names)} ({pd.to_datetime(df["Date"].iloc[0]).year})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    return df

if __name__ == "__main__":
    players = ['Aaron Judge', 'Cal Raleigh']
    df = create_cumulative_home_runs_graph(players, 2025)
