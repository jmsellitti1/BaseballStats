import statsapi
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

def get_home_run_dates(player_name, start_date, end_date):
    """Get all home run dates for a specific player within a date range."""
    team_id = get_player_team_id(player_name)
    if not team_id:
        return []
    
    try:
        schedule = statsapi.schedule(start_date=start_date, end_date=end_date, team=team_id)
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

def create_cumulative_home_runs_graph(player_names, start_date='2025-03-27', end_date='2025-09-28', 
                                    df_path='df_state.pkl', force_refresh=False):
    """
    Create a cumulative home runs comparison graph for multiple players.
    
    Args:
        player_names (list): List of player names to compare
        start_date (str): Start date for the season (YYYY-MM-DD)
        end_date (str): End date for the season (YYYY-MM-DD)
        df_path (str): Path to save/load the dataframe state
        force_refresh (bool): If True, regenerate data even if cached file exists
    
    Returns:
        pandas.DataFrame: The dataframe with cumulative home run data
    """
    
    if force_refresh and os.path.exists(df_path):
        os.remove(df_path)
        print("DataFrame state deleted for refresh.")
    
    if os.path.exists(df_path) and not force_refresh:
        print("Loading existing DataFrame state...")
        with open(df_path, 'rb') as f:
            df = pickle.load(f)
    else:
        print("Creating new DataFrame...")
        dates = pd.date_range(start=start_date, end=end_date)
        df_data = {'Date': dates}
        
        for player in player_names:
            df_data[player] = 0
        
        df = pd.DataFrame(df_data)
        
        for player in player_names:
            hr_dates = get_home_run_dates(player, start_date, end_date)
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
    plt.title(f'Cumulative Home Runs: {" vs. ".join(player_names)} ({pd.to_datetime(start_date).year})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    return df

if __name__ == "__main__":
    players = ['Aaron Judge', 'Cal Raleigh', 'Mookie Betts', 'Ronald Acuña Jr.']
    df = create_cumulative_home_runs_graph(players)
