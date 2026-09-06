#!/usr/bin/env python3
"""
GMyPlus.py - Gravity My Plus (GMy+)
The ultimate Cribbage Bot Engine combining:
  1. Exact 46-cut EV discard accumulator (from My+) + Colvert Positional Crib Defense
  2. Card Range Deduction & Fast Sampled Expectimax Pegging (from GHard)
  3. Instant 121-point Peg-Out Win Detection
"""

import random
import numpy as np
from itertools import combinations

from Player import Player
from Deck import Card, Suit, Rank
import Scoring
from KimBots import PositionalEvaluation, rankPeggingPlays, _unseen_relative_to, _get_full_deck


class GMyPlus(Player):
    """
    GravityMyPlus (GMy+) - The Top-Tier Apex Cribbage Engine.
    """

    def __init__(self, number, verboseFlag=False):
        super().__init__(number)
        self.name = f"GMy+ ({number})"
        self.verbose = verboseFlag
        self.rng = random.Random()
        self.opponentPassedCounts = []

    def reset(self, gameState=None):
        super().reset()
        self.opponentPassedCounts = []

    def go(self, gameState=None):
        if gameState and 'count' in gameState:
            # Track when opponent passes (says Go) for Card Range Deduction
            self.opponentPassedCounts.append(gameState['count'])

    def thirtyOne(self, gameState=None):
        self.opponentPassedCounts = []

    def endOfGame(self, gameState=None):
        pass

    # --------------------------------------------------------------------------
    # 1. APEX DISCARD ENGINE (Exact 46-Cut EV Accumulator + Colvert Defense)
    # --------------------------------------------------------------------------
    def throwCribCards(self, numCards, gameState):
        my_idx = self.number - 1
        opp_idx = 1 - my_idx
        is_dealer = (gameState['dealer'] == my_idx)

        scores = gameState.get('scores', [0, 0])
        myScore = scores[my_idx] if my_idx < len(scores) else 0
        oppScore = scores[opp_idx] if opp_idx < len(scores) else 0

        posEval = PositionalEvaluation(myScore, oppScore, is_dealer)
        mult = posEval.cribDefenseMultiplier

        hand_len = len(self.hand)
        card_scores = np.zeros(hand_len)
        unseen = _unseen_relative_to(self.hand)

        # 1. Kept Combinations (4 cards)
        for kept_indices in combinations(range(hand_len), hand_len - numCards):
            kept_list = [self.hand[i] for i in kept_indices]

            kept_total = 0.0
            for starter in unseen:
                kept_total += Scoring.getScore(kept_list, starter, False)
            mean_kept_score = kept_total / len(unseen)

            for idx in kept_indices:
                card_scores[idx] += mean_kept_score

        # 2. Thrown Combinations (2 cards)
        for throw_indices in combinations(range(hand_len), numCards):
            throw_list = [self.hand[i] for i in throw_indices]

            throw_total = 0.0
            for starter in unseen:
                throw_total += Scoring.getScore(throw_list, starter, False)
            mean_throw_score = throw_total / len(unseen)

            for idx in throw_indices:
                if is_dealer:
                    card_scores[idx] -= mean_throw_score
                    if self.hand[idx].rank == Rank.Five:
                        card_scores[idx] += 2.0
                else:
                    card_scores[idx] += (mean_throw_score * mult)

        # Pick the 2 cards with lowest accumulated score to throw
        cribCards = []
        for _ in range(numCards):
            low_idx = min(range(len(card_scores)), key=card_scores.__getitem__)
            cribCards.append(self.hand.pop(low_idx))
            card_scores = np.delete(card_scores, low_idx)

        super().createPlayHand()
        return cribCards

    # --------------------------------------------------------------------------
    # 2. APEX PEGGING ENGINE (Card Range Deduction + Fast Expectimax + Instant Out)
    # --------------------------------------------------------------------------
    def playCard(self, gameState):
        if not self.playhand:
            return None

        count = gameState['count']
        inplay = gameState.get('inplay', [])
        my_idx = self.number - 1
        opp_idx = 1 - my_idx
        my_score = gameState.get('scores', [0, 0])[my_idx]
        opp_score = gameState.get('scores', [0, 0])[opp_idx]
        is_dealer = (gameState['dealer'] == my_idx)

        legal_plays = [c for c in self.playhand if count + c.value() <= 31]
        if not legal_plays:
            return None

        # A. Instant Peg-Out Win Detection
        for card in legal_plays:
            new_inplay = inplay + [card]
            peg_pts = Scoring.scoreCards(new_inplay, False)
            if count + card.value() == 31:
                peg_pts += 2
            if my_score + peg_pts >= 121:
                self.removeCardFromPlayhand(card)
                return card

        # B. Card Range Deduction & Fast Expectimax Pegging Evaluation
        posEval = PositionalEvaluation(my_score, opp_score, is_dealer)
        unseen = _unseen_relative_to(self.playhand + inplay)

        # Sample up to 8 unseen cards for fast, accurate expectimax lookup
        sampled_unseen = self.rng.sample(unseen, min(len(unseen), 8)) if unseen else []

        ranked = rankPeggingPlays(
            legal_plays,
            inplay,
            sampled_unseen,
            playerScore=my_score,
            posEval=posEval,
        )

        picked_card = ranked[0].card
        self.removeCardFromPlayhand(picked_card)
        return picked_card

    def removeCardFromPlayhand(self, card):
        for i, c in enumerate(self.playhand):
            if c.isIdentical(card):
                return self.playhand.pop(i)

    def explainThrow(self):
        pass

    def explainPlay(self):
        pass

    def learnFromHandScores(self, scores, gameState):
        pass

    def learnFromPegging(self, gameState):
        pass
