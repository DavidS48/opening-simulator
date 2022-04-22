import io
import json
import random
import logging
import time

import chess.pgn
import requests

class OutOfBook(Exception):
    pass


class MoveGenerator:
    def __init__(self, player_db_access, selection_strategy):
        self.player_db_access = player_db_access
        self.selection_strategy = selection_strategy
        self.min_book_moves = 5

    def get_move(self, board):
        if out_of_master_book(board):
            raise OutOfBook()
        explorer_moves = get_db_moves(board, self.player_db_access)
        if len(explorer_moves) == 0:
            raise OutOfBook()
        explorer_move = self.selection_strategy(explorer_moves)
        return chess.Move.from_uci(explorer_move["uci"])

def get_db_moves(board, request_generator):
    retries = 0
    while True:
        try:
            request, params = request_generator(board)
            resp = requests.get(request, params = params)
            return json.loads(resp.content.decode("utf-8"))["moves"]
        except json.decoder.JSONDecodeError as e:
            #print(f"Failed to get {board.fen()}")
            if retries < 10:
                retries += 1
                time.sleep(120)
            else:
                raise e



class LichessDbMoves:
    def __init__(self, speed = "rapid", rating= "2000"):
        self.speed = speed
        self.rating = rating

    def __call__(self, board):
        params = {"fen": board.fen(), "variant": "standard", "speeds[]": [self.speed], "ratings[]": [self.rating]}
        return "https://explorer.lichess.ovh/lichess", params


def master_db_moves(board):
    params = {"fen": board.fen()}
    return "https://explorer.lichess.ovh/masters", params


def pick_random(exp_moves):
    moves = []
    counts = []
    for exp_move in exp_moves:
        move_count = exp_move["white"] + exp_move["black"] + exp_move["draws"]
        moves.append(exp_move)
        counts.append(move_count)
    return random.choices(moves, weights = counts)[0]

def pick_top(exp_moves):
    return exp_moves[0]

def out_of_master_book(board, min_count = 5):
    explorer_moves = get_db_moves(board, master_db_moves)
    count = 0
    for exp_move in explorer_moves:
        count += exp_move["white"] + exp_move["black"] + exp_move["draws"]
    return count < min_count


#FEN = input("Enter /EN:")

def run_game(FEN):
    book_move_generator = MoveGenerator(master_db_moves, pick_top)
    lichess_move_generator = MoveGenerator(LichessDbMoves(), pick_random)
    board = chess.Board(FEN)
    if board.turn == chess.WHITE:
        player_to_move = 0
        player_move_generators = [lichess_move_generator, book_move_generator]
    else:
        player_to_move = 1
        player_move_generators = [book_move_generator, lichess_move_generator]
    white_move = "  "
    while True:
        try:
            move_generator = player_move_generators[player_to_move]
            move = move_generator.get_move(board)
            if player_to_move == 1:
                pass
                #print(board.fullmove_number, white_move, board.san(move))
            else:
                white_move = board.san(move)
            board.push(move)
            player_to_move = 1 - player_to_move
        except OutOfBook:
            return board


scotch_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3"
ruy_fen = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
open_sicilian_fen = "rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3"

e5_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
sicilian_fen = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
caro_fen = "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"

def analyze_fen(FEN):
    depths = []
    while len(depths) < 40:
        try:
            board = run_game(FEN)
            depths.append(board.fullmove_number - 1)
            #print(depths)
        except json.decoder.JSONDecodeError:
            pass
            #logging.exception("Something went wrong")
            time.sleep(60)
        #except:
        #    break
    print(depths)
    print(sum(depths) / len(depths))

def print_endpoint(board):
    if board.turn == chess.BLACK:
        last_player = "White"
    else:
        last_player = "Black"
    print(f"{last_player} went entirely out of book on move {board.fullmove_number}")
    print(board)

analyze_fen(e5_fen)
analyze_fen(sicilian_fen)
analyze_fen(caro_fen)
