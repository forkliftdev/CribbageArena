#!/usr/bin/env python3
"""
Tournament.py - Runs a Round-Robin Tournament for Kim's Kribbage bots in CribbageArena.

Tiers:
  1. Easy (tuned to beat Random comfortably)
  2. Medium (tuned for ~60% win rate)
  3. Hard (Kim Hard EV engine)
  4. Expert / Myrmidon (CribbageArena benchmark rollout bot)
  5. Random (Baseline benchmark)
"""

import sys
import argparse
import numpy as np

from Cribbage import Cribbage
from KimBots import (
    KimEasyBot,
    KimMediumBot,
    KimHardBot,
    MyrmidonBot,
)
from PlayerRandom import PlayerRandom
from Myrmidon import Myrmidon
from MyrmidonPlus import MyrmidonPlus


def create_bot(bot_class, number):
    if bot_class == Myrmidon:
        return Myrmidon(number, 5, verboseFlag=False)
    if bot_class == MyrmidonPlus:
        return MyrmidonPlus(number, verboseFlag=False)
    try:
        return bot_class(number, verboseFlag=False)
    except TypeError:
        return bot_class(number, False)


def run_matchup(bot_class_1, bot_class_2, num_games=20, verbose=False):
    p1_wins = 0
    p2_wins = 0
    p1_margin_total = 0

    for g in range(num_games):
        p1 = create_bot(bot_class_1, 1)
        p2 = create_bot(bot_class_2, 2)

        game = Cribbage([p1, p2], verboseFlag=False)
        game.dealer = g % 2

        game.playGame()
        winner = game.checkWin()

        if winner == 1:
            p1_wins += 1
        elif winner == 2:
            p2_wins += 1

        margin = p1.pips - p2.pips
        p1_margin_total += margin

    return {
        'p1_wins': p1_wins,
        'p2_wins': p2_wins,
        'avg_margin': p1_margin_total / num_games,
    }


def run_tournament(num_games_per_matchup=20, include_random=True, include_myrmidon_plus=True):
    bot_classes = [
        MyrmidonPlus,
        MyrmidonBot,
        KimHardBot,
        KimMediumBot,
        KimEasyBot,
    ]

    if include_random:
        bot_classes.append(PlayerRandom)

    num_bots = len(bot_classes)
    bot_names = [create_bot(bot_classes[i], 1).name.replace(" (1)", "") for i in range(num_bots)]

    print("=" * 70)
    print(f"   KIM'S KRIBBAGE ARENA TOURNAMENT")
    print(f"   {num_bots} Bots | {num_games_per_matchup} Games per Matchup (121-pt matches)")
    print("=" * 70)

    win_matrix = np.zeros((num_bots, num_bots), dtype=int)
    margin_matrix = np.zeros((num_bots, num_bots), dtype=float)

    total_matchups = (num_bots * (num_bots - 1)) // 2
    completed = 0

    for i in range(num_bots):
        for j in range(i + 1, num_bots):
            completed += 1
            print(f"[{completed}/{total_matchups}] {bot_names[i]} vs {bot_names[j]}...", end="", flush=True)

            res = run_matchup(bot_classes[i], bot_classes[j], num_games=num_games_per_matchup)
            win_matrix[i, j] = res['p1_wins']
            win_matrix[j, i] = res['p2_wins']
            margin_matrix[i, j] = res['avg_margin']
            margin_matrix[j, i] = -res['avg_margin']

            print(f" ({res['p1_wins']} - {res['p2_wins']})")

    total_wins = np.sum(win_matrix, axis=1)
    total_losses = np.sum(win_matrix, axis=0)
    total_games = total_wins + total_losses
    win_pct = (total_wins / total_games) * 100.0
    avg_margins = np.mean(margin_matrix, axis=1)

    indices = np.argsort(-win_pct)

    print("\n" + "=" * 70)
    print(f"   FINAL TOURNAMENT STANDINGS")
    print("=" * 70)
    print(f"{'Rank':<5} {'Bot Name':<20} {'Wins':<8} {'Losses':<8} {'Win %':<10} {'Avg Margin':<12}")
    print("-" * 70)

    for rank, idx in enumerate(indices, start=1):
        print(
            f"{rank:<5} {bot_names[idx]:<20} {total_wins[idx]:<8} {total_losses[idx]:<8} "
            f"{win_pct[idx]:>5.1f}%     {avg_margins[idx]:>+6.2f} pts"
        )
    print("=" * 70)

    print("\nHEAD-TO-HEAD WIN MATRIX (Row vs Column Wins):")
    header = f"{'':<20}" + "".join([f"{bot_names[i][:8]:>10}" for i in range(num_bots)])
    print(header)
    for i in range(num_bots):
        row_str = f"{bot_names[i]:<20}"
        for j in range(num_bots):
            if i == j:
                row_str += f"{'--':>10}"
            else:
                row_str += f"{win_matrix[i, j]:>10}"
        print(row_str)
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Kim's Kribbage Tournament in CribbageArena")
    parser.add_argument(
        "--games",
        type=int,
        default=20,
        help="Number of 121-pt games per matchup pair (default: 20)",
    )
    parser.add_argument(
        "--h2h",
        action="store_true",
        help="Run head-to-head 500-game match MyrmidonPlus vs Myrmidon",
    )
    args = parser.parse_args()

    if args.h2h:
        num_games = args.games if args.games != 20 else 500
        print("=" * 70)
        print(f"   HEAD-TO-HEAD BENCHMARK: MyrmidonPlus vs Original Myrmidon ({num_games} Games)")
        print("=" * 70)
        res = run_matchup(MyrmidonPlus, Myrmidon, num_games=num_games)
        p1_pct = (res['p1_wins'] / num_games) * 100.0
        p2_pct = (res['p2_wins'] / num_games) * 100.0
        print(f"\nRESULTS after {num_games} 121-pt games:")
        print(f"  MyrmidonPlus : {res['p1_wins']} wins ({p1_pct:.1f}%)")
        print(f"  Myrmidon (Orig): {res['p2_wins']} wins ({p2_pct:.1f}%)")
        print(f"  Average Point Differential: {res['avg_margin']:+.2f} pts/game for MyrmidonPlus")
        print("=" * 70)
    else:
        run_tournament(num_games_per_matchup=args.games)
