import random

# נגדיר את הצורות והערכים כקבועים
SUITS = ['♠', '♥', '♦', '♣']  # Spades, Hearts, Diamonds, Clubs
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

class Card:
    """מייצג קלף בודד"""
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        
    def get_struct_values(self):
        # המרה של Rank למספר 1-13
        rank_map = {'A': 1, 'J': 11, 'Q': 12, 'K': 13}
        if self.rank in rank_map:
            r = rank_map[self.rank]
        else:
            r = int(self.rank)
            
        # המרה של Suit למספר 0-3 (תלוי במיפוי שאתה מחליט, נניח לפי הסדר ברשימה שלך)
        suit_map = {'♠': 0, '♥': 1, '♦': 2, '♣': 3} # Spades, Hearts, Diamonds, Clubs
        s = suit_map[self.suit]
        
        return r, s
    def __str__(self):
        # הדפסה יפה: למשל "A♥" או "10♠"
        return f"{self.rank}{self.suit}"

    def get_value(self):
        """מחזיר את ערך הקלף (בלאק ג'ק)"""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11 # ערך ראשוני, יטופל בהמשך אם נשרף
        else:
            return int(self.rank)

class Deck:
    """מייצג חבילת קלפים"""
    def __init__(self):
        self.cards = []
        self.reset() # יצירת חבילה חדשה

    def reset(self):
        """יוצר חבילה חדשה של 52 קלפים ומערבב"""
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        """שולף קלף אחד מהחבילה"""
        if len(self.cards) > 0:
            return self.cards.pop()
        return None

class Hand:
    def __init__(self):
        self.cards = []
        self.value = 0

    def add_card(self, card):
        self.cards.append(card)
        # לא מחשבים כאן, אלא כשמבקשים get_value

    def calculate_value(self):
        val = 0
        aces = 0
        for card in self.cards:
            v = card.get_value() # וודא ש-Card.get_value מחזיר 11 לאס ו-10 לתמונות
            val += v
            if card.rank == 'A': aces += 1
        
        # לוגיקה קריטית: מורידים 10 רק אם באמת חרגנו מ-21
        while val > 21 and aces > 0:
            val -= 10
            aces -= 1
        return val
            
    def get_value(self):
        self.value = self.calculate_value()
        return self.value
    
class GameState:
    def __init__(self):
        self.deck = Deck()
        self.deck.reset() # מערבב חבילה חדשה
        self.player_hand = Hand()
        self.dealer_hand = Hand()
# --- בדיקה מהירה (Main) ---
# הקוד הזה ירוץ רק אם מריצים את הקובץ הזה ישירות
if __name__ == "__main__":
    print("--- Testing Game Logic ---")
    
    # 1. יצירת חבילה
    deck = Deck()
    print(f"Deck created with {len(deck.cards)} cards.")
    
    # 2. יצירת יד לשחקן
    player_hand = Hand()
    
    # 3. חלוקת שני קלפים
    card1 = deck.deal()
    card2 = deck.deal()
    player_hand.add_card(card1)
    player_hand.add_card(card2)
    
    print(f"Player Hand: {player_hand}")
    
    # 4. בדיקת לוגיקה של אס (בדיקה ידנית)
    # נצור יד מלאכותית עם שני אסים כדי לראות שאחד הופך ל-1
    print("\n--- Testing Ace Logic ---")
    test_hand = Hand()
    test_hand.add_card(Card('A', '♠')) # 11
    test_hand.add_card(Card('A', '♥')) # 11 -> יגרום לפיצוץ -> הופך ל 12
    print(f"Two Aces Hand: {test_hand}") # אמור לצאת 12