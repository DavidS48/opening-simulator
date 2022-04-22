import io
import json
import random
import logging
import time

import chess.pgn
import click
import requests


class OutOfBook(Exception):
    pass


class MoveGenerator:
    def __init__(self, db_request_generator, selection_strategy):
        self.db_request_generator = db_request_generator
        self.selection_strategy = selection_strategy
        self.min_book_moves = 5

    def get_move(self, board):
        if out_of_master_book(board):
            raise OutOfBook()
        explorer_moves = get_db_moves(board, self.db_request_generator)
        if len(explorer_moves) == 0:
            raise OutOfBook()
        explorer_move = self.selection_strategy(explorer_moves)
        return chess.Move.from_uci(explorer_move["uci"])


def get_db_moves(board, request_generator):
    retries = 0
    while True:
        try:
            request, params = request_generator(board)
            resp = requests.get(request, params=params)
            return json.loads(resp.content.decode("utf-8"))["moves"]
        except json.decoder.JSONDecodeError as e:
            # We aren't checking for http error codes, so this is normally the
            # first clue that we've been throttled by the Lichess API.
            # Waiting for 60+ seconds is considered polite so we go for 120..
            if retries < 10:
                retries += 1
                time.sleep(120)
            else:
                raise e


class LichessDbRequest:
    """Constructs base url and parameters for requesting information on the
    given position from the lichess opening explorer API for given speed and
    rating.""" 
    def __init__(self, speed, rating):
        self.speed = speed
        self.rating = rating

    def __call__(self, board):
        params = {
            "fen": board.fen(),
            "variant": "standard",
            "speeds[]": [self.speed],
            "ratings[]": [self.rating],
        }
        return "https://explorer.lichess.ovh/lichess", params


def master_db_request(board):
    """Constructs base url and parameters for requesting information on the
    given position from the lichess opening explorer API using the master
    games collection.""" 
    params = {"fen": board.fen()}
    return "https://explorer.lichess.ovh/masters", params


def pick_random(exp_moves):
    """Select a random move from the list, weighted by the number of times they
    were played."""
    moves = []
    counts = []
    for exp_move in exp_moves:
        move_count = exp_move["white"] + exp_move["black"] + exp_move["draws"]
        moves.append(exp_move)
        counts.append(move_count)
    return random.choices(moves, weights=counts)[0]


def pick_top(exp_moves):
    """Select the top move from the list."""
    return exp_moves[0]


def out_of_master_book(board, min_count=5):
    """Check whether the master db has at least min_count games for the given
    position."""
    explorer_moves = get_db_moves(board, master_db_request)
    count = 0
    for exp_move in explorer_moves:
        count += exp_move["white"] + exp_move["black"] + exp_move["draws"]
    return count < min_count




def run_game(FEN, db_speed, db_rating):
    """Play out a game from the given FEN, assuming that the player who has
    just moved is playing top master moves and the player who is to move is
    playing random Lichess moves."""
    book_move_generator = MoveGenerator(master_db_request, pick_top)
    lichess_move_generator = MoveGenerator(LichessDbRequest(db_speed, db_rating), pick_random)
    board = chess.Board(FEN)
    game_score = []
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
                game_score.append(f"{board.fullmove_number} {white_move} {board.san(move)}")
            else:
                white_move = board.san(move)
            board.push(move)
            player_to_move = 1 - player_to_move
        except OutOfBook:
            return board, game_score

fens_dict = {
        "scotch_w" : "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",
        "ruy_w" : "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        "open_sicilian_w" : "rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",

        "e5_b" : "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "sicilian_b" : "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "caro_b": "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
}

@click.command()
@click.option("--num-games", default=40)
@click.option("--fen", default="", help="FEN for starting positon, or name of a FEN in the intenal fens dict.")
@click.option("--speed", default="rapid")
@click.option("--rating", default="2000")
def analyze_fen(fen, num_games, speed, rating):
    if fen in fens_dict:
        final_fen = fens_dict[fen]
    elif fen == "":
        final_fen = input("FEN:")
    else:
        final_fen = fen
    depths = []
    while len(depths) < num_games:
        try:
            board, _ = run_game(final_fen, speed, rating)
            depths.append(board.fullmove_number - 1)
        except:
            logging.exception("Something went wrong.")
            break
    print(depths)
    print(sum(depths) / len(depths))


def print_endpoint(board):
    if board.turn == chess.BLACK:
        last_player = "White"
    else:
        last_player = "Black"
    print(f"{last_player} went entirely out of book on move {board.fullmove_number}")
    print(board)

if __name__ == "__main__":
    analyze_fen()
