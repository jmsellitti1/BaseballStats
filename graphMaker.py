import statsapi
import pandas as pd
from tqdm import tqdm
import os
import pickle

def update_cumulative(df, player, hr_dates):
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'])
    df_dates = df['Date']

    total = 0
    last_idx = 0
    for hr_date in hr_dates:
        matches = df_dates[df_dates == hr_date]
        idx = matches.index[0]
        if idx - 1 >= last_idx:
            df.loc[last_idx:idx-1, player] = total
        total += 1
        df.loc[idx, player] = total
        last_idx = idx + 1
    if last_idx < len(df):
        df.loc[last_idx:, player] = total

def delete_df_state(df_path):
    if os.path.exists(df_path):
        os.remove(df_path)
        print("DataFrame state deleted.")
    else:
        print("No DataFrame state file found to delete.")
        
df_path = 'df_state.pkl'
# Uncomment the line below to create a new dataframe every time
# delete_df_state(df_path)

if os.path.exists(df_path):
    print("Loading existing DataFrame state...")
    with open(df_path, 'rb') as f:
        df = pickle.load(f)
else:
    dates = pd.date_range(start='2025-03-27', end='2025-09-28')
    df = pd.DataFrame({
        'Date': dates,
        'Aaron Judge': 0,
        'Cal Raleigh': 0
    })

    yankees_id = statsapi.lookup_team('nyy')[0]['id']
    mariners_id = statsapi.lookup_team('sea')[0]['id']
    y_schedule = statsapi.schedule(start_date = '2025-03-27', end_date = '2025-09-28', team=yankees_id)
    m_schedule = statsapi.schedule(start_date = '2025-03-27', end_date = '2025-09-28', team=mariners_id)

    judge_hr_dates = []
    for game in tqdm(y_schedule, desc="Processing Yankees Games"):
        scoring_plays = statsapi.game_scoring_play_data(game['game_id'])
        for play in scoring_plays['plays']:
            if play['result']['description'].startswith(('Aaron Judge homers', 'Aaron Judge hits a grand slam')):
                judge_hr_dates.append(game['game_date'])

    raleigh_hr_dates = []
    for game in tqdm(m_schedule, desc="Processing Mariners Games"):
        scoring_plays = statsapi.game_scoring_play_data(game['game_id'])
        for play in scoring_plays['plays']:
            if play['result']['description'].startswith(('Cal Raleigh homers', 'Cal Raleigh hits a grand slam')):
                raleigh_hr_dates.append(game['game_date'])


    update_cumulative(df, 'Aaron Judge', judge_hr_dates)
    update_cumulative(df, 'Cal Raleigh', raleigh_hr_dates)

    with open(df_path, 'wb') as f:
        pickle.dump(df, f)

import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.plot(df['Date'], df['Aaron Judge'], label='Aaron Judge')
plt.plot(df['Date'], df['Cal Raleigh'], label='Cal Raleigh')
plt.xlabel('Date')
plt.ylabel('Home Runs (Cumulative)')
plt.title('Cumulative Home Runs: Aaron Judge vs Cal Raleigh (2025)')
plt.legend()
plt.tight_layout()
plt.show()

