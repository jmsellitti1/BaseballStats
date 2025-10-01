import statsapi  # pyright: ignore[reportMissingImports]
import pandas as pd
from tqdm import tqdm
import os
import pickle
import matplotlib.pyplot as plt

CURRENT_SEASON = 2026 # Only using regular season games for now so can assume 2025 is completed

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

def get_player_team_id(player_name, season):
    """Get the team ID for a given player name."""
    players = statsapi.lookup_player(player_name, season=season)
    if not players:
        print(f"Warning: Player '{player_name}' not found")
        return 0
    
    return players[0]['currentTeam']['id']

def extract_player_stat_from_boxscore(boxscore_data, player_name, stat_type):
    """
    Extract a specific stat for a player from box score data.

    Args:
        boxscore_data: The box score data from statsapi.boxscore_data()
        player_name: Name of the player to look up
        stat_type: The stat to extract (e.g., 'homeRuns', 'hits', 'runs', 'rbi', 'strikeOuts')

    Returns:
        float: The stat value, or 0 if not found
    """
    player_data = None
    for team in ['away', 'home']:
        for id, data in boxscore_data[team]['players'].items():
            if data['person']['fullName'].lower() == player_name.lower():
                player_data = data
                break
        if player_data is not None:
            break
    if player_data is None:  # Player not in boxscore
        return 0

    position = player_data.get('position', {}).get('abbreviation', None)
    stats = player_data.get('stats', {})

    batting_stats = stats.get('batting', {})
    pitching_stats = stats.get('pitching', {})

    try:
        if position == 'P':
            if stat_type in pitching_stats and pitching_stats[stat_type] is not None:
                return float(pitching_stats[stat_type])
        else:
            if stat_type in batting_stats and batting_stats[stat_type] is not None:
                return float(batting_stats[stat_type])
    except (KeyError, TypeError, ValueError):
        pass

    # Fallback: search pitching and batting categories and return the first non-zero value
    for category_stats in [batting_stats, pitching_stats]:
        if stat_type in category_stats and category_stats[stat_type] is not None:
            try:
                value = float(category_stats[stat_type])
                if value > 0:  # Only return non-zero values in fallback
                    return value
            except (ValueError, TypeError):
                continue
    return 0

def get_player_stats_from_schedule(player_name, season, stat_type):
    """
    Get all stat values for a specific player from their team's schedule using box score data.
    Intelligently determines whether to use batting or pitching stats based on context.
    
    Args:
        player_name: Name of the player to look up
        season: The season year
        stat_type: The stat to extract (e.g., 'homeRuns', 'hits', 'runs', 'rbi', 'strikeOuts')
    
    Returns:
        list: List of tuples (game_date, stat_value)
    """
    team_id = get_player_team_id(player_name, season)
    
    schedule = statsapi.schedule(season=season, team=team_id)
    schedule = [game for game in schedule if game['game_type'] == 'R']
    stat_dates = []
        
    for game in tqdm(schedule, desc=f"Counting stat \"{stat_type}\" for {player_name}"):
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

        # Add new players if needed
        new_players = [player for player in player_names if player not in df.columns]
        if new_players:
            print(f"Adding new players: {new_players}")
            for player in new_players:
                df[player] = 0
                stat_dates = get_player_stats_from_schedule(player, season, stat_type)
                update_cumulative(df, player, stat_dates)

        with open(df_path, 'wb') as f:
            pickle.dump(df, f)
        print(f"DataFrame state saved to {df_path}")
    else:
        print("Creating new DataFrame...")
        team = 0
        for player in player_names:
            team = get_player_team_id(player, season)
            if team > 0:
                break
        if team == 0:
            print("Warning: No valid players found in list")
        schedule = statsapi.schedule(season=season, team=team)
        schedule = [game for game in schedule if game['game_type'] == 'R']
        start_date = pd.to_datetime(schedule[0]['game_date'])
        end_date = pd.to_datetime(schedule[-1]['game_date'])
        dates = pd.date_range(start=start_date, end=end_date)
        df_data = {'Date': dates}

        for player in player_names:
            df_data[player] = 0

        df = pd.DataFrame(df_data)

        for player in player_names:
            stat_dates = get_player_stats_from_schedule(player, season, stat_type)
            update_cumulative(df, player, stat_dates)

        with open(df_path, 'wb') as f:
            pickle.dump(df, f)
        print(f"DataFrame state saved to {df_path.split('/')[-1]}")

    # Only plot the requested subset of players
    plt.figure(figsize=(12, 6))
    for player in player_names:
        if player in df.columns:
            plt.plot(df['Date'], df[player], label=player)
    plt.xlabel('Date')
    plt.ylabel(f'{stat_display_name} (Cumulative)')
    plt.title(f'Cumulative {stat_display_name}: {' vs. '.join(player_names)} ({pd.to_datetime(df['Date'].iloc[0]).year})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Option to save/delete pkl file
    save_or_delete = input("Save Data? (y/n): ")
    if save_or_delete.lower() == 'y' or not save_or_delete:
        print("DataFrame save confirmed")
    else:
        os.remove(df_path)
        print("DataFrame state deleted")

if __name__ == "__main__":
    players = ['Aaron Judge', 'Cal Raleigh', 'Shohei Ohtani']
    create_cumulative_stats_graph(players, 2025, 'rbi', 'RBI\'s')