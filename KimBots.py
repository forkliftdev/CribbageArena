#!/usr/bin/env python3
"""
KimBots.py - Implements Kim's Kribbage bots in Python for CribbageArena.

Includes:
  - Positional Play Engine (Colvert 26-Point Theory & Schell Par Holes)
  - Discard Evaluator (Monte Carlo EV + Positional Crib Defense)
  - Smart Pegging Evaluator (Card Deduction + Tactical Pegging Heuristics)
  - Myrmidon Heuristic Rollout Bot
  - 4 Main Opponent Tiers: Easy (beats Random), Medium (~60% win rate), Hard (Kim Hard), Expert (Myrmidon)
"""

import random
from itertools import combinations
from enum import Enum

from Player import Player
from Deck import Card, Suit, Rank
import Scoring


class StrategicPosture(Enum):
    OFFENSE = 1
    DEFENSE = 2
    DESPERATION_DEFENSE = 3
    ENDGAME_OUT_COUNT = 4


class PositionalEvaluation:
    def __init__(self, playerScore, opponentScore, isDealer):
        self.playerScore = playerScore
        self.opponentScore = opponentScore
        self.isDealer = isDealer

        if playerScore >= 105 or opponentScore >= 105:
            self.street = 5
            self.parHole = 121
            self.delta = playerScore - 105
            self.posture = StrategicPosture.ENDGAME_OUT_COUNT
        else:
            if playerScore < 18 and opponentScore < 18:
                self.street = 1
                self.parHole = 18 if isDealer else 9
            elif playerScore < 44 and opponentScore < 44:
                self.street = 2
                self.parHole = 44 if isDealer else 31
            elif playerScore < 70 and opponentScore < 70:
                self.street = 3
                self.parHole = 70 if isDealer else 57
            else:
                self.street = 4
                self.parHole = 96 if isDealer else 83

            self.delta = playerScore - self.parHole
            if self.street == 4 and self.delta <= -8:
                self.posture = StrategicPosture.DESPERATION_DEFENSE
            elif self.delta < 0:
                self.posture = StrategicPosture.DEFENSE
            else:
                self.posture = StrategicPosture.OFFENSE

    @property
    def cribDefenseMultiplier(self):
        if self.posture == StrategicPosture.OFFENSE:
            return 1.0
        elif self.posture == StrategicPosture.DEFENSE:
            return 1.35
        elif self.posture == StrategicPosture.DESPERATION_DEFENSE:
            return 1.8
        elif self.posture == StrategicPosture.ENDGAME_OUT_COUNT:
            return 1.0 if self.isDealer else 1.6
        return 1.0


def _get_full_deck():
    cards = []
    for suit in Suit:
        for rank in Rank:
            cards.append(Card(rank, suit))
    return cards


def _unseen_relative_to(knownCards):
    known_uids = {c.uid() for c in knownCards}
    return [c for c in _get_full_deck() if c.uid() not in known_uids]


class RankedDiscard:
    def __init__(self, keep, discard, expectedHandValue, expectedCribValue, cribIsMine, posEval=None):
        self.keep = keep
        self.discard = discard
        self.expectedHandValue = expectedHandValue
        self.expectedCribValue = expectedCribValue
        self.cribIsMine = cribIsMine
        self.posEval = posEval

    @property
    def expectedValue(self):
        mult = self.posEval.cribDefenseMultiplier if self.posEval else 1.0
        cribVal = self.expectedCribValue if self.cribIsMine else (-self.expectedCribValue * mult)
        return self.expectedHandValue + cribVal


def rankDiscards(sixCardHand, cribIsMine, sampleSize=10, rng=None, posEval=None):
    if rng is None:
        rng = random.Random()

    unseen = _unseen_relative_to(sixCardHand)
    results = []

    for combo in combinations(sixCardHand, 2):
        discard = list(combo)
        discard_uids = {c.uid() for c in discard}
        keep = [c for c in sixCardHand if c.uid() not in discard_uids]

        handTotal = 0
        cribTotal = 0

        for _ in range(sampleSize):
            sample = rng.sample(unseen, 3)
            starter = sample[0]
            crib = discard + [sample[1], sample[2]]

            handTotal += Scoring.getScore(keep, starter, False)
            cribTotal += Scoring.getScore(crib, starter, False)

        results.append(
            RankedDiscard(
                keep=keep,
                discard=discard,
                expectedHandValue=handTotal / sampleSize,
                expectedCribValue=cribTotal / sampleSize,
                cribIsMine=cribIsMine,
                posEval=posEval,
            )
        )

    results.sort(key=lambda r: r.expectedValue, reverse=True)
    return results


class RankedPeggingPlay:
    def __init__(self, card, immediateScore, expectedOpponentResponse, tacticalAdjustment=0.0, tacticalTag=None):
        self.card = card
        self.immediateScore = immediateScore
        self.expectedOpponentResponse = expectedOpponentResponse
        self.tacticalAdjustment = tacticalAdjustment
        self.tacticalTag = tacticalTag

    @property
    def netValue(self):
        return self.immediateScore - self.expectedOpponentResponse + self.tacticalAdjustment


def rankPeggingPlays(legalPlays, stackSoFar, unseenCards, playerScore=0, posEval=None):
    results = []

    for card in legalPlays:
        newStack = stackSoFar + [card]
        newTotal = sum(c.value() for c in newStack)
        immediate = Scoring.scoreCards(newStack, False)

        if playerScore + immediate >= 121:
            results.append(
                RankedPeggingPlay(
                    card=card,
                    immediateScore=immediate,
                    expectedOpponentResponse=0.0,
                    tacticalAdjustment=1000.0,
                    tacticalTag='out_count_win',
                )
            )
            continue

        possibleReplies = [c for c in unseenCards if newTotal + c.value() <= 31]
        if not possibleReplies:
            expectedReply = 0.0
        else:
            replyScores = [Scoring.scoreCards(newStack + [r], False) for r in possibleReplies]
            expectedReply = sum(replyScores) / len(replyScores)

        tacticalAdj = 0.0
        tag = None

        if not stackSoFar:
            if card.rank == Rank.Five:
                tacticalAdj -= 3.0
                tag = 'avoid_five_lead'
        else:
            if newTotal == 11:
                tacticalAdj += 0.8
                tag = 'magic_eleven'
            elif newTotal == 21:
                tacticalAdj += 0.6
                tag = 'magic_twenty_one'

        results.append(
            RankedPeggingPlay(
                card=card,
                immediateScore=immediate,
                expectedOpponentResponse=expectedReply,
                tacticalAdjustment=tacticalAdj,
                tacticalTag=tag,
            )
        )

    results.sort(key=lambda r: r.netValue, reverse=True)
    return results


class BaseKimBot(Player):
    def __init__(self, number, botTierName, verbose=False, verboseFlag=False, *args, **kwargs):
        super().__init__(number)
        self.name = botTierName
        self.verbose = verbose or verboseFlag
        self.rng = random.Random()

    def removeCardFromHand(self, card):
        for i, c in enumerate(self.hand):
            if c.isIdentical(card):
                return self.hand.pop(i)

    def removeCardFromPlayhand(self, card):
        for i, c in enumerate(self.playhand):
            if c.isIdentical(card):
                return self.playhand.pop(i)

    def explainThrow(self, numCards=2, gameState=None):
        pass

    def explainPlay(self, numCards=1, gameState=None):
        pass

    def learnFromHandScores(self, scores, gameState):
        pass

    def learnFromPegging(self, gameState):
        pass


class KimEasyBot(BaseKimBot):
    """
    Easy Bot (Smart Beginner): Has common-sense guardrails (never gives 5s or pairs to opponent crib,
    never leads a 5), but has zero crib synergy and purely reactive pegging.
    """
    def __init__(self, number, verbose=False, verboseFlag=False, *args, **kwargs):
        super().__init__(number, "Easy", verbose=verbose, verboseFlag=verboseFlag)

    def throwCribCards(self, numCards, gameState):
        isDealer = (gameState['dealer'] == self.number - 1)
        ranked = rankDiscards(self.hand, cribIsMine=isDealer, rng=self.rng)
        
        candidates = ranked[:8]  # top half
        if not isDealer:
            # Guardrail: Never throw a 5 into the opponent's crib if any non-5 discard exists!
            non_five = [r for r in candidates if not any(c.rank == Rank.Five for c in r.discard)]
            if non_five:
                candidates = non_five
            # Avoid gifting pairs to opponent crib if alternative exists
            non_pair = [r for r in candidates if r.discard[0].rank != r.discard[1].rank]
            if non_pair:
                candidates = non_pair
                
        picked = self.rng.choice(candidates)
        for c in picked.discard:
            self.removeCardFromHand(c)
        super().createPlayHand()
        return picked.discard

    def playCard(self, gameState):
        count = gameState['count']
        inplay = gameState.get('inplay', [])
        legal = [c for c in self.playhand if count + c.value() <= 31]
        if not legal:
            return None

        # Prefer immediate scoring play if available
        scoring = []
        for c in legal:
            pts = Scoring.scoreCards(inplay + [c], False)
            scoring.append((c, pts))

        scoring.sort(key=lambda item: item[1], reverse=True)
        if scoring[0][1] > 0:
            picked_card = scoring[0][0]
        else:
            # Guardrail: NEVER lead a 5 if any non-5 card is legal!
            if not inplay:
                non_fives = [c for c in legal if c.rank != Rank.Five]
                picked_card = self.rng.choice(non_fives) if non_fives else legal[0]
            else:
                picked_card = self.rng.choice(legal)

        self.removeCardFromPlayhand(picked_card)
        return picked_card


class KimMediumBot(BaseKimBot):
    """
    Medium Bot (Porch Player / Aunt Kim): Plays sensible, friendly cribbage.
    Discards: Picks from top 4 EV options (50% #1, 30% #2, 10% #3, 10% #4); guards opponent crib.
    Pegging: Avoids 5-leads, doesn't give away easy 15s/31s; takes 70% #1 / 30% #2 Expectimax plays.
    """
    def __init__(self, number, verbose=False, verboseFlag=False, *args, **kwargs):
        super().__init__(number, "Medium", verbose=verbose, verboseFlag=verboseFlag)

    def throwCribCards(self, numCards, gameState):
        isDealer = (gameState['dealer'] == self.number - 1)
        ranked = rankDiscards(self.hand, cribIsMine=isDealer, rng=self.rng)
        
        candidates = ranked[:4]
        if not isDealer:
            non_five = [r for r in candidates if not any(c.rank == Rank.Five for c in r.discard)]
            if non_five:
                candidates = non_five

        r = self.rng.random()
        if r < 0.50 or len(candidates) == 1:
            picked = candidates[0]
        elif r < 0.80 and len(candidates) > 1:
            picked = candidates[1]
        elif r < 0.90 and len(candidates) > 2:
            picked = candidates[2]
        else:
            picked = candidates[-1]

        for c in picked.discard:
            self.removeCardFromHand(c)
        super().createPlayHand()
        return picked.discard

    def playCard(self, gameState):
        count = gameState['count']
        inplay = gameState.get('inplay', [])
        legal = [c for c in self.playhand if count + c.value() <= 31]
        if not legal:
            return None

        unseen = _unseen_relative_to(self.playhand + inplay)
        sampled = self.rng.sample(unseen, min(len(unseen), 6)) if unseen else []
        ranked = rankPeggingPlays(legal, inplay, sampled)

        # 70% #1 pick, 30% #2 pick
        if len(ranked) > 1 and self.rng.random() < 0.30:
            picked_card = ranked[1].card
        else:
            picked_card = ranked[0].card

        self.removeCardFromPlayhand(picked_card)
        return picked_card


class KimHardBot(BaseKimBot):
    """
    Hard Bot (Club Player - formerly GMedium):
    Discards: 65% #1, 25% #2, 10% #3 from Colvert Par-Hole EV.
    Pegging: 65% #1, 35% #2 Expectimax pegging with Card Range Deduction.
    """
    def __init__(self, number, verbose=False, verboseFlag=False, *args, **kwargs):
        super().__init__(number, "Hard", verbose=verbose, verboseFlag=verboseFlag)

    def throwCribCards(self, numCards, gameState):
        isDealer = (gameState['dealer'] == self.number - 1)
        scores = gameState.get('scores', [0, 0])
        myScore = scores[self.number - 1] if self.number <= len(scores) else 0
        oppScore = scores[1 - (self.number - 1)] if len(scores) > 1 else 0

        posEval = PositionalEvaluation(myScore, oppScore, isDealer)
        ranked = rankDiscards(self.hand, cribIsMine=isDealer, rng=self.rng, posEval=posEval)
        
        # Pick from top 3 discards: 65% #1, 25% #2, 10% #3
        roll = self.rng.random()
        if len(ranked) > 2 and roll < 0.10:
            picked = ranked[2]
        elif len(ranked) > 1 and roll < 0.35:
            picked = ranked[1]
        else:
            picked = ranked[0]

        for c in picked.discard:
            self.removeCardFromHand(c)
        super().createPlayHand()
        return picked.discard

    def playCard(self, gameState):
        count = gameState['count']
        legal = [c for c in self.playhand if count + c.value() <= 31]
        if not legal:
            return None

        isDealer = (gameState['dealer'] == self.number - 1)
        scores = gameState.get('scores', [0, 0])
        myScore = scores[self.number - 1] if self.number <= len(scores) else 0
        oppScore = scores[1 - (self.number - 1)] if len(scores) > 1 else 0

        posEval = PositionalEvaluation(myScore, oppScore, isDealer)
        unseen = _unseen_relative_to(self.playhand + gameState.get('inplay', []))
        sampled_unseen = self.rng.sample(unseen, min(len(unseen), 8)) if unseen else []
        ranked = rankPeggingPlays(legal, gameState.get('inplay', []), sampled_unseen, playerScore=myScore, posEval=posEval)

        # 65% top pick, 35% 2nd pick
        if len(ranked) > 1 and self.rng.random() < 0.35:
            picked = ranked[1]
        else:
            picked = ranked[0]

        self.removeCardFromPlayhand(picked.card)
        return picked.card


class MyrmidonBot(BaseKimBot):
    """
    Expert Bot (Myrmidon from CribbageArena): Uses 5-sample rollouts for discarding
    and heuristic card scoring for pegging.
    """
    def __init__(self, number, numSims=5, verbose=False, verboseFlag=False, *args, **kwargs):
        super().__init__(number, "Expert (Myrmidon)", verbose=verbose, verboseFlag=verboseFlag)
        self.numSims = max(numSims, 1)

    def _randomStarter(self):
        hand_uids = {c.uid() for c in self.hand}
        unseen = [c for c in _get_full_deck() if c.uid() not in hand_uids]
        return self.rng.choice(unseen)

    def throwCribCards(self, numCards, gameState):
        isDealer = (gameState['dealer'] == self.number - 1)
        cardScores = [0.0] * len(self.hand)

        for combo in combinations(self.hand, len(self.hand) - numCards):
            for _ in range(self.numSims):
                starter = self._randomStarter()
                score = Scoring.getScore(list(combo), starter, False)
                for j, c in enumerate(self.hand):
                    if c in combo:
                        cardScores[j] += score

        for combo in combinations(self.hand, numCards):
            for _ in range(self.numSims):
                starter = self._randomStarter()
                score = Scoring.getScore(list(combo), starter, False)
                for j, c in enumerate(self.hand):
                    if c in combo:
                        if isDealer:
                            cardScores[j] -= score
                            if c.rank == Rank.Five:
                                cardScores[j] += 2.0
                        else:
                            cardScores[j] += score

        indices = list(range(len(self.hand)))
        indices.sort(key=lambda idx: cardScores[idx])
        discard_indices = sorted(indices[:numCards], reverse=True)

        cribCards = []
        for idx in discard_indices:
            cribCards.append(self.hand.pop(idx))

        super().createPlayHand()
        return cribCards

    def playCard(self, gameState):
        count = gameState['count']
        countCards = gameState.get('inplay', [])
        cardScores = [0.0] * len(self.playhand)

        if not self.playhand:
            return None

        for i, card in enumerate(self.playhand):
            if count + card.value() <= 31:
                newStack = countCards + [card]
                cardScores[i] = 10.0 * Scoring.scoreCards(newStack, False) + card.rank.value
                newVal = count + card.value()
                if newVal == 5 or newVal == 10 or newVal == 21:
                    cardScores[i] = max(1.0, cardScores[i] - 10.0)
                if newVal < 5:
                    cardScores[i] += 15.0

        if max(cardScores) > 0.0:
            best_idx = max(range(len(cardScores)), key=lambda idx: cardScores[idx])
            return self.playhand.pop(best_idx)
        return None
