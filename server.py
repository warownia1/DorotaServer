import random
import socket
import traceback
from collections import deque
from contextlib import contextmanager
from string import ascii_uppercase

import gevent.server


def get_random_id(k=5):
    return ''.join(random.choices(ascii_uppercase, k=k))


players = dict()
messages_pool = list()
clients = list()
game: 'Game' = None

PREPARATION = 'PREPARATION'
GAME = 'GAME'
FINISHED = 'FINISHED'


class Game:
    def __init__(self):
        self.players = deque()
        self.ready_players = set()
        self.questions = list()
        self.answers = list()
        self.question_count = dict()
        self.answer_count = dict()
        self.state = PREPARATION
        self.scores = dict()

    def add_player(self, player):
        self.players.append(player)
        self.question_count[player.id] = 0
        self.answer_count[player.id] = 0
        self.scores[player.id] = 0

    def add_question(self, player_id, question):
        if self.question_count[player_id] < 4:
            self.questions.append(question)
        print(f'current questions: {self.questions}')

    def add_answer(self, player_id, answer):
        if self.answer_count[player_id] < 12:
            self.answers.append(answer)
        print(f'current answers: {self.answers}')

    def set_ready(self, player_id):
        # if (self.question_count[player_id] == 4
        #         and self.answer_count[player_id] == 12):
        self.ready_players.add(player_id)

    @property
    def all_ready(self):
        return len(self.ready_players) == len(self.players)

    def init_game(self):
        random.shuffle(self.players)
        random.shuffle(self.questions)
        random.shuffle(self.answers)
        self.state = GAME

    def play_turn(self):
        cur_plr = self.players.pop()
        for player in self.players:
            ans = self.pop_answer()
            send_msg(player.client, f'GotAnswer;{ans}')
        self.players.appendleft(cur_plr)
        quest = self.pop_question()
        send_msg(cur_plr.client, f'GotQuestion;{quest}')

    def pop_question(self):
        return self.questions.pop()

    def pop_answer(self):
        return self.answers.pop()

    def insert_answer(self, answer):
        index = random.randint(0, len(self.answers))
        self.answers.insert(index, answer)

    @property
    def current_player(self):
        return self.players[0]

    def start_turn(self):
        pass

    def give_point(self, player_id):
        self.players[player_id] += 1

    @property
    def game_over(self):
        return not self.questions


class Player:
    def __init__(self):
        while True:
            self.id = get_random_id()
            if self.id not in players: break
        players[self.id] = self
        self.name = self.id
        self.client = None

    def __repr__(self):
        return f'Player({self.id}, {self.name})'


class Message:
    __slots__ = ['command', 'player_id', 'content', 'client']

    @property
    def player(self):
        return players.get(self.player_id, None)


@contextmanager
def message(data=';;;'):
    if messages_pool:
        msg = messages_pool.pop()
    else:
        msg = Message()
    try:
        msg.command, msg.player_id, msg.content = data.split(';', 2)
        yield msg
    finally:
        messages_pool.append(msg)


def client_connected(client: socket.socket, address):
    clients.append(client)
    print(f'new connection from {address}')
    while True:
        try:
            text = recv_msg(client)
            if not text: raise ConnectionError("No data from client.")
        except ConnectionError:
            break
        print(f'{address} sent "{text}"')
        with message(text) as msg:
            try:
                callback = globals()['do_' + msg.command]
            except KeyError as e:
                print(e)
                send_msg(client, 'Error;InvalidCommand')
                continue
            try:
                callback(client, msg)
            except Exception:
                traceback.print_exc()
                continue
    print(f"client {address} disconnected")


def do_SignIn(client, msg: Message):
    plr = players.get(msg.player_id)
    if plr is None: plr = Player()
    print(f'player {plr.id} signed in')
    if plr.client: plr.client.close()
    plr.client = client
    plr.name = msg.content
    global game
    if game is None: game = Game()
    game.add_player(plr)
    send_msg(client, f'SignedIn;{plr.id}')


def do_GetPlayerName(client, msg: Message):
    plr = players.get(msg.content)
    if plr is None: return
    send_msg(client, f'PlayerName;{plr.id};{plr.name}')


def do_GetPlayers(client, msg: Message):
    plrs = ','.join(plr.id for plr in game.players)
    send_msg(client, f'Players;{plrs}')


def do_SetName(client, msg: Message):
    msg.player.name = msg.content


def do_SetReady(client, msg: Message):
    game.set_ready(msg.player_id)
    if game.all_ready:
        for client in clients:
            send_msg(client, f'GameStarted')
        game.play_turn()


def do_AddQuestion(client, msg: Message):
    game.add_question(msg.player_id, msg.content)


def do_AddAnswer(client, msg: Message):
    game.add_answer(msg.player_id, msg.content)


def do_SendChat(client, msg: Message):
    for client in clients:
        send_msg(client, f'NewChat;{msg.player.name}: {msg.content}')


def do_Vote(client, msg: Message):
    if msg.player_id == game.current_player.id:
        winner_id = msg.content
        game.give_point(winner_id)
        score = game.scores[winner_id]
        for plr in game.players:
            send_msg(plr.client, f'UpdateScore;{winner_id};{score}')
        game.play_turn()


def do_Reroll(client, msg: Message):
    game.insert_answer(msg.content)
    new_answer = game.pop_answer()
    send_msg(client, f'GotAnswer;{new_answer}')


def recv_msg(client):
    size_bytes = b''.join(client.recv(1) for _ in range(4))
    frame_size = int.from_bytes(size_bytes, 'big')
    buffer = b''
    while len(buffer) < frame_size:
        buffer += client.recv(frame_size - len(buffer))
    return buffer.decode()


def send_msg(client, data):
    data = data.encode()
    client.sendall(len(data).to_bytes(4, 'big'))
    client.sendall(data)


ADDRESS = ('', 7575)

if __name__ == '__main__':
    server = gevent.server.StreamServer(ADDRESS, client_connected)
    server.start()
    print(f'server started {server.server_host}:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()


