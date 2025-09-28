import statsapi  # pyright: ignore[reportMissingImports]
import pandas as pd
from tqdm import tqdm
import os
import pickle
import matplotlib.pyplot as plt

CURRENT_SEASON = 2025

def update_cumulative(df, player, stat_dates):
    """Update cumulative stat counts for a player in the dataframe."""
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'])
    df_dates = df['Date']

    total = 0
    last_idx = 0
    for stat_date, stat_value in stat_dates:
        matches = df_dates[df_dates == stat_date]
        if matches.empty:
            print(f"Warning: No match found for {stat_date} for player {player}")
            continue
        idx = matches.index[0]
        if idx - 1 >= last_idx:
            df.loc[last_idx:idx-1, player] = total
        total += stat_value
        df.loc[idx, player] = total
        last_idx = idx + 1
    if last_idx < len(df):
        df.loc[last_idx:, player] = total

def get_player_team_id(player_name):
    """Get the team ID for a given player name."""
    players = statsapi.lookup_player(player_name)
    if not players:
        print(f"Warning: Player '{player_name}' not found")
        return None
    
    return players[0]['currentTeam']['id']

def find_player_in_boxscore(boxscore_data, player_name):
    """Find a player in the box score data by name."""
    for team in ['away', 'home']:
        for player_id, player_data in boxscore_data[team]['players'].items():
            if player_data['person']['fullName'].lower() == player_name.lower():
                return player_id, player_data
    return None, None

def extract_player_stat_from_boxscore(boxscore_data, player_name, stat_type):
    """
    Extract a specific stat for a player from box score data.
    Automatically detects whether the stat is batting or pitching.
    
    Args:
        boxscore_data: The box score data from statsapi.boxscore_data()
        player_name: Name of the player to look up
        stat_type: The stat to extract (e.g., 'homeRuns', 'hits', 'runs', 'rbi', 'strikeOuts')
    
    Returns:
        float: The stat value, or 0 if not found
    """
    player_id, player_data = find_player_in_boxscore(boxscore_data, player_name)
    
    if not player_data:
        return 0
    
    for category in ['batting', 'pitching']:
        if category in player_data['stats']:
            stats = player_data['stats'][category]
            if stat_type in stats and stats[stat_type] is not None:
                try:
                    return float(stats[stat_type])
                except (ValueError, TypeError):
                    continue
    return 0

def get_player_stats_from_schedule(player_name, season, stat_type):
    """
    Get all stat values for a specific player from their team's schedule using box score data.
    Automatically detects whether the stat is batting or pitching.
    
    Args:
        player_name: Name of the player to look up
        season: The season year
        stat_type: The stat to extract (e.g., 'homeRuns', 'hits', 'runs', 'rbi', 'strikeOuts')
    
    Returns:
        list: List of tuples (game_date, stat_value)
    """
    team_id = get_player_team_id(player_name)
    
    schedule = statsapi.schedule(season=season, team=team_id)
    schedule = [game for game in schedule if game['game_type'] == 'R']
    stat_dates = []
        
    for game in tqdm(schedule, desc=f"Processing Games for {player_name}"):
        try:
            boxscore_data = statsapi.boxscore_data(game['game_id'])
            stat_value = extract_player_stat_from_boxscore(boxscore_data, player_name, stat_type)
            
            if stat_value > 0:
                stat_dates.append((game['game_date'], stat_value))
                
        except Exception as e:
            print(f"Error processing game {game['game_id']}: {e}")
            continue
            
    return stat_dates


def create_cumulative_stats_graph(player_names, season, stat_type, stat_display_name=None):
    """
    Create a cumulative stats comparison graph for multiple players.
    
    Args:
        player_names (list): List of player names to compare
        season (int): The year/season (e.g., 2025)
        stat_type (str): The stat to track (e.g., 'homeRuns', 'hits', 'runs', 'rbi', 'strikeOuts')
        stat_display_name (str): Display name for the stat (defaults to stat_type)
    
    Returns:
        pandas.DataFrame: The dataframe with cumulative stat data
    """
    if stat_display_name is None:
        stat_display_name = stat_type
    
    data_folder = 'data'
    df_path = os.path.join(data_folder, f'{stat_type}_{season}.pkl')
    os.makedirs(data_folder, exist_ok=True)
    
    if season == CURRENT_SEASON and os.path.exists(df_path):
        print(f"Forcing rebuild for current season ({season}) to get latest data...")
        os.remove(df_path)
    
    if os.path.exists(df_path):
        print("Loading existing DataFrame state...")
        with open(df_path, 'rb') as f:
            df = pickle.load(f)
        
        new_players = [player for player in player_names if player not in df.columns]
        if new_players:
            print(f"Adding new players: {new_players}")
            for player in new_players:
                df[player] = 0
                stat_dates = get_player_stats_from_schedule(player, season, stat_type)
                update_cumulative(df, player, stat_dates)
            
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
            print(f"Getting {stat_type} data for {player}...")
            stat_dates = get_player_stats_from_schedule(player, season, stat_type)
            update_cumulative(df, player, stat_dates)
        
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
    plt.ylabel(f'{stat_display_name} (Cumulative)')
    plt.title(f'Cumulative {stat_display_name}: {" vs. ".join(player_names)} ({pd.to_datetime(df["Date"].iloc[0]).year})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    return df

if __name__ == "__main__":
    # Examples:
    players = ['Aaron Judge', 'Cal Raleigh']
    df = create_cumulative_stats_graph(players, 2025, 'homeRuns', 'Home Runs')
    
    # players = ['Aaron Judge', 'Cal Raleigh']
    # df = create_cumulative_stats_graph(players, 2025, 'hits', 'Hits')
    
    # players = ['Aaron Judge', 'Cal Raleigh']
    # df = create_cumulative_stats_graph(players, 2025, 'rbi', 'RBIs')
    
    # pitchers = ['Gerrit Cole', 'Shane Bieber']
    # df = create_cumulative_stats_graph(pitchers, 2025, 'strikeOuts', 'Strikeouts')
    
    # schedule = statsapi.schedule(team=147, season=CURRENT_SEASON)
    # schedule = [game for game in schedule if game['game_type'] == 'R']
    # print(statsapi.boxscore_data(schedule[0]['game_id']))