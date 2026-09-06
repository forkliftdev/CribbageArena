#!/usr/bin/env python3
"""
MegaTournament.py - Grand Tournament Runner with Granular Point Tracking

Tracks detailed statistics across all scoring arenas:
  1. Win / Loss / Win %
  2. Average Point Margin
  3. Hand Points (4-card kept hand scores)
  4. Crib Points (points scored in own crib)
  5. Opponent Crib Points (points conceded to opponent in their crib)
  6. Pegging Points (points scored during pegging phase & cut Nobs)
"""

import sys
import argparse
import multiprocessing
import numpy as np
from itertools import combinations

from Cribbage import Cribbage
from Scoring import getScore, scoreCards, Rank
from KimBots import (
    KimEasyBot,
    KimMediumBot,
    KimHardBot,
    MyrmidonBot,
)
from Myrmidon import Myrmidon
from MyrmidonPlus import MyrmidonPlus
from GMyPlus import GMyPlus
from PlayerRandom import PlayerRandom


class TrackedCribbage(Cribbage):
    def __init__(self, players, verboseFlag=False):
        super().__init__(players, verboseFlag=False)
        self.critic = None
        self.verbose = False
        self.stats = {
            1: {'hand': 0, 'crib': 0, 'pegging': 0},
            2: {'hand': 0, 'crib': 0, 'pegging': 0},
        }

    def playHand(self):
        self.deal()
        self.createCrib()
        self.cut()
        self.play()
        self.scoreHands()

    def cut(self, card=None):
        if card is None:
            self.deck.cut()
            self.starter = self.deck.cards.pop()
        else:
            self.starter = card
        if self.starter.rank is Rank.Jack:
            dealer_num = self.players[self.dealer].number
            self.players[self.dealer].pips += 2
            self.stats[dealer_num]['pegging'] += 2

    def scoreHands(self):
        for i in range(self.dealer + 1, self.dealer + 1 + len(self.players)):
            if self.checkWin():
                break
            player = self.players[i % len(self.players)]
            score = getScore(player.hand, self.starter, self.verbose)
            player.pips += score
            self.stats[player.number]['hand'] += score

        if not (self.checkWin()):
            cribScore = getScore(self.crib, self.starter, self.verbose)
            dealer_num = self.players[self.dealer].number
            self.players[self.dealer].pips += cribScore
            self.stats[dealer_num]['crib'] += cribScore

        for player in self.players:
            player.learnFromHandScores(
                [getScore(self.players[0].hand, self.starter, False),
                 getScore(self.players[1].hand, self.starter, False),
                 getScore(self.crib, self.starter, False)],
                self.gameState()
            )

    def play(self):
        self.playorder = []
        toPlay = (self.dealer + 1) % len(self.players)
        self.playorder = []

        while (any(len(player.playhand) > 0 for player in self.players)) and (not (self.checkWin())):
            self.inplay = []
            count = 0
            goCounter = 0

            while (count < 31) and (goCounter < 2) and (not (self.checkWin())):
                playedCard = self.players[toPlay].playCard(self.gameState())
                p_num = self.players[toPlay].number

                if playedCard is None:
                    if goCounter == 0:
                        goCounter = 1
                    else:
                        goCounter = 2
                        self.players[toPlay].pips += 1
                        self.stats[p_num]['pegging'] += 1
                else:
                    count += playedCard.value()
                    self.inplay.append(playedCard)
                    self.playorder.append(playedCard)
                    pts = scoreCards(self.inplay, self.verbose)
                    self.players[toPlay].pips += pts
                    self.stats[p_num]['pegging'] += pts
                    goCounter = 0

                toPlay = ((toPlay + 1) % len(self.players))
                self.players[toPlay].learnFromPegging(self.gameState())

            if goCounter == 2:
                for player in self.players:
                    player.go(self.gameState())

            if count == 31:
                for player in self.players:
                    player.thirtyOne(self.gameState())

            if self.checkWin():
                for player in self.players:
                    player.endOfGame(self.gameState())


def create_bot(bot_class, number):
    if bot_class == Myrmidon:
        return Myrmidon(number, 5, verboseFlag=False)
    if bot_class == MyrmidonPlus:
        return MyrmidonPlus(number, verboseFlag=False)
    if bot_class == GMyPlus:
        return GMyPlus(number, verboseFlag=False)
    try:
        return bot_class(number, verboseFlag=False)
    except TypeError:
        return bot_class(number, False)


def run_matchup(bot_class_1, bot_class_2, num_games=100):
    p1_wins = 0
    p2_wins = 0
    p1_margin_total = 0

    p1_stats = {'hand': 0, 'crib': 0, 'pegging': 0}
    p2_stats = {'hand': 0, 'crib': 0, 'pegging': 0}

    for g in range(num_games):
        p1 = create_bot(bot_class_1, 1)
        p2 = create_bot(bot_class_2, 2)

        game = TrackedCribbage([p1, p2], verboseFlag=False)
        game.dealer = g % 2

        game.playGame()
        winner = game.checkWin()

        if winner == 1:
            p1_wins += 1
        elif winner == 2:
            p2_wins += 1

        p1_margin_total += (p1.pips - p2.pips)

        for cat in ['hand', 'crib', 'pegging']:
            p1_stats[cat] += game.stats[1][cat]
            p2_stats[cat] += game.stats[2][cat]

    return {
        'p1_wins': p1_wins,
        'p2_wins': p2_wins,
        'avg_margin': p1_margin_total / num_games,
        'p1_stats': {cat: p1_stats[cat] / num_games for cat in p1_stats},
        'p2_stats': {cat: p2_stats[cat] / num_games for cat in p2_stats},
    }


def run_mega_tournament(num_games_per_matchup=50):
    bot_classes = [
        GMyPlus,
        KimHardBot,
        KimMediumBot,
        KimEasyBot,
    ]

    num_bots = len(bot_classes)
    bot_names = [create_bot(bot_classes[i], 1).name.replace(" (1)", "") for i in range(num_bots)]

    print("=" * 100)
    print(f"   GRAND KRIBBAGE ARENA TOURNAMENT & ARENA STATISTICAL BREAKDOWN")
    print(f"   {num_bots} Bots | {num_games_per_matchup} Games per Matchup (121-pt matches)")
    print("=" * 100)

    win_matrix = np.zeros((num_bots, num_bots), dtype=int)
    margin_matrix = np.zeros((num_bots, num_bots), dtype=float)

    tot_hand = np.zeros(num_bots, dtype=float)
    tot_crib = np.zeros(num_bots, dtype=float)
    tot_opp_crib = np.zeros(num_bots, dtype=float)
    tot_pegging = np.zeros(num_bots, dtype=float)
    matchup_counts = np.zeros(num_bots, dtype=int)

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

            tot_hand[i] += res['p1_stats']['hand']
            tot_crib[i] += res['p1_stats']['crib']
            tot_opp_crib[i] += res['p2_stats']['crib']
            tot_pegging[i] += res['p1_stats']['pegging']
            matchup_counts[i] += 1

            tot_hand[j] += res['p2_stats']['hand']
            tot_crib[j] += res['p2_stats']['crib']
            tot_opp_crib[j] += res['p1_stats']['crib']
            tot_pegging[j] += res['p2_stats']['pegging']
            matchup_counts[j] += 1

            print(f" ({res['p1_wins']} - {res['p2_wins']})", flush=True)

    total_wins = np.sum(win_matrix, axis=1)
    total_losses = np.sum(win_matrix, axis=0)
    total_games = total_wins + total_losses
    win_pct = (total_wins / total_games) * 100.0
    avg_margins = np.mean(margin_matrix, axis=1)

    avg_hand = tot_hand / matchup_counts
    avg_crib = tot_crib / matchup_counts
    avg_opp_crib = tot_opp_crib / matchup_counts
    avg_pegging = tot_pegging / matchup_counts

    indices = np.argsort(-win_pct)

    print("\n" + "=" * 100)
    print(f"   FINAL TOURNAMENT STANDINGS & SCORING ARENA BREAKDOWN")
    print("=" * 100)
    header = f"{'Rank':<5} {'Bot Name':<20} {'Wins':<7} {'Losses':<7} {'Win %':<8} {'Avg Margin':<11} {'Hand Pts':<10} {'Crib Pts':<10} {'Opp Crib':<10} {'Pegging':<10}"
    print(header)
    print("-" * 100)

    for rank, idx in enumerate(indices, start=1):
        print(
            f"{rank:<5} {bot_names[idx]:<20} {total_wins[idx]:<7} {total_losses[idx]:<7} "
            f"{win_pct[idx]:>5.1f}%   {avg_margins[idx]:>+6.2f} pts   "
            f"{avg_hand[idx]:>6.1f} pts  {avg_crib[idx]:>6.1f} pts  {avg_opp_crib[idx]:>6.1f} pts  {avg_pegging[idx]:>6.1f} pts"
        )
    print("=" * 100)

    print("\nHEAD-TO-HEAD WIN MATRIX (Row vs Column Wins):")
    h_header = f"{'':<20}" + "".join([f"{bot_names[i][:8]:>10}" for i in range(num_bots)])
    print(h_header)
    for i in range(num_bots):
        row_str = f"{bot_names[i]:<20}"
        for j in range(num_bots):
            if i == j:
                row_str += f"{'--':>10}"
            else:
                row_str += f"{win_matrix[i, j]:>10}"
        print(row_str)
    print("=" * 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Grand Kribbage Arena Tournament")
    parser.add_argument(
        "--games",
        type=int,
        default=500,
        help="Number of 121-pt games per matchup pair (default: 500)",
    )
    args = parser.parse_args()

    run_mega_tournament(num_games_per_matchup=args.games)
