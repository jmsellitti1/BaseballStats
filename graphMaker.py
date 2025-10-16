from genericpath import exists
import statsapi  # pyright: ignore[reportMissingImports]
import pandas as pd
from tqdm import tqdm
import os
import pickle
import matplotlib.pyplot as plt
from unidecode import unidecode

CURRENT_SEASON = 2026 # Only using regular season games for now so can assume 2025 is completed

def update_cumulative(df, player, stat_dates):
    """Update cumulative stat counts for a player in the dataframe."""
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'])
    df_dates = df['Date']

    last_idx = 0
    last_value = 0
    for stat_date, cumulative_value in stat_dates:
        matches = df_dates[df_dates == stat_date]
        if matches.empty:
            print(f"Warning: No match found for {stat_date} for player {player}")
            continue
        idx = matches.index[0]
        if idx - 1 >= last_idx:
            df.loc[last_idx:idx-1, player] = last_value
        if cumulative_value == 0 and last_value > 0:
            df.loc[idx, player] = last_value
        else:
            df.loc[idx, player] = cumulative_value
            last_value = cumulative_value
        last_idx = idx + 1
    if last_idx < len(df):
        df.loc[last_idx:, player] = last_value

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
            box_name = unidecode(data['person']['fullName']).strip().lower()
            search_name = unidecode(player_name).strip().lower()
            if box_name == search_name:
                player_data = data
                break
        if player_data is not None:
            break
    if player_data is None:  # Player not in boxscore
        return 0

    # Get cumulative stat from seasonStats
    season_stats = player_data.get('seasonStats', {})
    if player_data.get('position', {}).get('abbreviation') == 'P':
        category = 'pitching'
    else:
        category = 'batting'
    if stat_type in season_stats[category]:
        value = season_stats[category][stat_type]
        if value is not None and value != '-.--':
            try:
                return float(value)
            except (ValueError, TypeError):
                pass


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
    if team_id == 0: # Player not found
        return []
    schedule = statsapi.schedule(season=season, team=team_id)
    schedule = [game for game in schedule if game['game_type'] == 'R']
    stat_dates = []
        
    for game in tqdm(schedule, desc=f"Counting stat \"{stat_type}\" for {player_name} in {season}"):
        try:
            boxscore_data = statsapi.boxscore_data(game['game_id'])
            cumulative_value = extract_player_stat_from_boxscore(boxscore_data, player_name, stat_type)
            stat_dates.append((game['game_date'], cumulative_value))
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
        
    else:
        print("Creating new DataFrame...")
        team = 0
        for player in player_names:
            team = get_player_team_id(player, season)
            if team > 0:
                break
        if team == 0:
            print("Warning: No valid players found in list")
            return None
        schedule = statsapi.schedule(season=season, team=team)
        schedule = [game for game in schedule if game['game_type'] == 'R']
        start_date = pd.to_datetime(schedule[0]['game_date'])
        end_date = pd.to_datetime(schedule[-1]['game_date'])
        dates = pd.date_range(start=start_date, end=end_date)
        df_data = {'Date': dates}
        df = pd.DataFrame(df_data)
        new_players = player_names
        
    # Track original columns for possible revert
    original_columns = df.columns.copy()
    actually_added_players = []
    if new_players:
        print(f"Adding new players: {', '.join(new_players)}")
        for player in new_players:
            stat_dates = get_player_stats_from_schedule(player, season, stat_type)
            if stat_dates:
                df[player] = 0.0
                update_cumulative(df, player, stat_dates)
                actually_added_players.append(player)
    plot_players = [player for player in player_names if player in df.columns]
    for player in plot_players:
        plt.plot(df['Date'], df[player], label=player)
    plt.xlabel('Date')
    plt.ylabel(f'{stat_display_name} (Cumulative)')
    plt.title(f'Cumulative {stat_display_name}: {' vs. '.join(plot_players)} ({pd.to_datetime(df['Date'].iloc[0]).year})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    if actually_added_players:
        save_or_delete = input(f"Save Data with new players {', '.join(actually_added_players)}? (y/n): ")
        if save_or_delete.lower() == 'y' or not save_or_delete:
            with open(df_path, 'wb') as f:
                pickle.dump(df, f)
            print(f"DataFrame state saved to {df_path}")
        else:
            df = df[original_columns]
            print("DataFrame reverted to previous state; new players not saved.")
    else:
        print("No new players added; DataFrame unchanged.")

if __name__ == "__main__":
    # players = ['Aaron Judge', 'Cal Raleigh', 'Shohei Ohtani', 'Anthony Volpe']
    # create_cumulative_stats_graph(players, 2024, 'homeRuns', 'Home Runs')
    
    pitchers = ['Max Fried', 'Tarik Skubal', 'Paul Skenes', 'Test Player']
    create_cumulative_stats_graph(pitchers, 2025, 'era', 'ERA')