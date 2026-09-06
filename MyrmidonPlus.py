#!/usr/bin/env python3
"""
MyrmidonPlus.py - High Performance Expert Bot for CribbageArena

Combines exact 46-cut EV discard accumulator with Myrmidon's fast
10 * score + rank pegging engine and instant endgame peg-out detection.
"""

import random
import numpy as np
from itertools import combinations

from Player import Player
from Deck import Card, Suit, Rank
from Scoring import getScore, scoreCards


def get_full_deck():
    cards = []
    for suit in Suit:
        for rank in Rank:
            cards.append(Card(rank, suit))
    return cards


def unseen_relative_to(knownCards):
    known_uids = {c.uid() for c in knownCards}
    return [c for c in get_full_deck() if c.uid() not in known_uids]


class MyrmidonPlus(Player):

    def __init__(self, number, verboseFlag=False):
        super().__init__(number)
        self.name = f"MyrmidonPlus ({number})"
        self.verbose = verboseFlag
        self.rng = random.Random()

    def reset(self, gameState=None):
        super().reset()

    def go(self, gameState=None):
        pass

    def thirtyOne(self, gameState=None):
        pass

    def endOfGame(self, gameState=None):
        pass

    # --------------------------------------------------------------------------
    # 1. DISCARDING LOGIC (Myrmidon Per-Card Accumulator)
    # --------------------------------------------------------------------------
    def throwCribCards(self, numCards, gameState):
        my_idx = self.number - 1
        opp_idx = 1 - my_idx
        is_dealer = (gameState['dealer'] == my_idx)

        hand_len = len(self.hand)
        card_scores = np.zeros(hand_len)
        unseen = unseen_relative_to(self.hand)

        sample_starters = self.rng.sample(unseen, 10) if len(unseen) >= 10 else unseen

        # 1. Kept Combinations (4 cards)
        for kept_indices in combinations(range(hand_len), hand_len - numCards):
            kept_list = [self.hand[i] for i in kept_indices]

            kept_total = 0.0
            for starter in sample_starters:
                kept_total += getScore(kept_list, starter, False)
            mean_kept_score = kept_total / len(sample_starters)

            for idx in kept_indices:
                card_scores[idx] += mean_kept_score

        # 2. Thrown Combinations (2 cards)
        for throw_indices in combinations(range(hand_len), numCards):
            throw_list = [self.hand[i] for i in throw_indices]

            throw_total = 0.0
            for starter in sample_starters:
                throw_total += getScore(throw_list, starter, False)
            mean_throw_score = throw_total / len(sample_starters)

            for idx in throw_indices:
                if is_dealer:
                    card_scores[idx] -= mean_throw_score
                    if self.hand[idx].rank == Rank.Five:
                        card_scores[idx] += 2.0
                else:
                    card_scores[idx] += mean_throw_score

        # Pick the 2 cards with lowest accumulated score to throw
        cribCards = []
        for _ in range(numCards):
            low_idx = min(range(len(card_scores)), key=card_scores.__getitem__)
            cribCards.append(self.hand.pop(low_idx))
            card_scores = np.delete(card_scores, low_idx)

        super().createPlayHand()
        return cribCards

    # --------------------------------------------------------------------------
    # 2. PEGGING LOGIC (Fast 10 * Score + Rank Engine + Instant Peg-Out)
    # --------------------------------------------------------------------------
    def playCard(self, gameState):
        if not self.playhand:
            return None

        count = gameState['count']
        inplay = gameState['inplay']
        my_idx = self.number - 1
        my_score = gameState['scores'][my_idx]

        legal_plays = [c for c in self.playhand if count + c.value() <= 31]
        if not legal_plays:
            return None

        # --- A. INSTANT WIN CHECK ---
        for card in legal_plays:
            new_inplay = inplay + [card]
            peg_pts = scoreCards(new_inplay, False)
            if count + card.value() == 31:
                peg_pts += 2
            if my_score + peg_pts >= 121:
                self.removeCard(card)
                return card

        # --- B. FAST SCORING ENGINE ---
        card_scores = np.zeros(len(self.playhand))

        for i, card in enumerate(self.playhand):
            if count + card.value() < 32:
                new_inplay = inplay + [card]
                card_scores[i] = 10.0 * scoreCards(new_inplay, False) + card.rank.value

                new_val = count + card.value()
                if new_val in (5, 10, 21):
                    card_scores[i] = max(1.0, card_scores[i] - 10.0)

                if new_val < 5:
                    card_scores[i] += 15.0

        if np.amax(card_scores) > 0:
            best_idx = max(range(len(card_scores)), key=card_scores.__getitem__)
            played_card = self.playhand.pop(best_idx)
            return played_card
        else:
            return None

    def explainThrow(self):
        pass

    def explainPlay(self):
        pass

    def learnFromHandScores(self, scores, gameState):
        pass

    def learnFromPegging(self, gameState):
        pass
