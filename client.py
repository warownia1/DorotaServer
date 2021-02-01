"""
"""

import time
import sys

import socketio
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import (
  QVBoxLayout, QLabel, QLineEdit, QPushButton,
  QAbstractItemView)


DEFAULT_SERVER = "https://dorota-game.herokuapp.com"
sio = socketio.Client()

QtGui.QIcon.setThemeName("breeze")
QtGui.QIcon.setThemeSearchPaths(
  QtGui.QIcon.themeSearchPaths() + ['./icons']
)


class LoginWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    layout = QVBoxLayout()
    self.setLayout(layout)
    layout.addStretch(1)
    layout.addWidget(QLabel("username"))
    self.username_input = QLineEdit()
    layout.addWidget(self.username_input)
    layout.addWidget(QLabel("room code"))
    self.code_input = QLineEdit()
    layout.addWidget(self.code_input)
    layout.addStretch(1)
    button = QPushButton("Join")
    layout.addWidget(button)
    button.clicked.connect(self.join_room)

  @QtCore.Slot()
  def join_room(self):
    def callback(data):
      if data['status'] != 'ok':
        return print(data)
      global room_code
      room_code = data['roomcode']
      lobby_widget.set_room_code(data['roomcode'])
      lobby_widget.add_players(data['players'])
      lobby_widget.set_is_host(data['host'] == sio.get_sid())
      window_layout.setCurrentWidget(lobby_widget)

    sio.connect(DEFAULT_SERVER)
    time.sleep(0.5)
    code = self.code_input.text().upper()
    username = self.username_input.text()
    lobby_widget.clear_players()
    sio.emit("join-room", (code, username), callback=callback)


class LobbyWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    layout = QVBoxLayout()
    self.room_code_label = QtWidgets.QLabel("")
    layout.addWidget(self.room_code_label)
    self.players = QtWidgets.QListWidget()
    self.players.setSelectionMode(QAbstractItemView.NoSelection)
    layout.addWidget(self.players)
    self.start_button = QtWidgets.QPushButton("Start")
    self.start_button.clicked.connect(self.start_game)
    layout.addWidget(self.start_button)
    self.setLayout(layout)

  def set_room_code(self, value):
    self.room_code_label.setText(value)

  def set_is_host(self, value):
    self.start_button.setEnabled(value)

  def add_player(self, user_id, username):
    icon = QtGui.QIcon.fromTheme('face-smile')
    item = QtWidgets.QListWidgetItem(icon, username)
    item.user_id = user_id
    self.players.addItem(item)

  def add_players(self, players):
    for player in players:
      self.add_player(player['id'], player['username'])

  def clear_players(self):
    self.players.clear()

  @QtCore.Slot()
  def start_game(self):
    def callback(data):
      if data['status'] != 'ok': return print(data)
    sio.emit('start-game', (room_code,), callback=callback)


class PreparationWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    self.min_questions = 0
    self.min_answers = 0
    layout = QVBoxLayout()
    self.setLayout(layout)

    layout.addWidget(QLabel("Questions"))
    self.questions = QtWidgets.QListWidget()
    layout.addWidget(self.questions)
    self.question_textbox = QLineEdit()
    layout.addWidget(self.question_textbox)

    buttons_layout = QtWidgets.QHBoxLayout()
    icon = QtGui.QIcon.fromTheme('list-add')
    button = QPushButton(icon, "Add")
    button.clicked.connect(self.add_question)
    buttons_layout.addWidget(button)
    icon = QtGui.QIcon.fromTheme('list-remove')
    button = QPushButton(icon, 'Remove')
    button.clicked.connect(self.remove_question)
    buttons_layout.addWidget(button)
    layout.addLayout(buttons_layout)

    layout.addWidget(QLabel("Answers"))
    self.answers = QtWidgets.QListWidget()
    layout.addWidget(self.answers)
    self.answer_textbox = QLineEdit()
    layout.addWidget(self.answer_textbox)

    buttons_layout = QtWidgets.QHBoxLayout()
    icon = QtGui.QIcon.fromTheme('list-add')
    button = QPushButton(icon, "Add")
    button.clicked.connect(self.add_answer)
    buttons_layout.addWidget(button)
    icon = QtGui.QIcon.fromTheme('list-remove')
    button = QPushButton(icon, 'Remove')
    button.clicked.connect(self.remove_answer)
    buttons_layout.addWidget(button)
    icon = QtGui.QIcon.fromTheme('go-next')
    self.send_button = QPushButton(icon, "Send")
    self.send_button.clicked.connect(self.send_questions)
    buttons_layout.addWidget(self.send_button)
    layout.addLayout(buttons_layout)

  def set_num_players(self, num_players):
    self.min_questions = 3
    self.min_answers = 3  * (num_players - 1)

  @QtCore.Slot()
  def add_question(self):
    text: str = self.question_textbox.text()
    if text:
      if not text.endswith('?'):
        text += '?'
      self.questions.addItem(text)
      self.question_textbox.clear()

  @QtCore.Slot()
  def remove_question(self):
    self.questions.takeItem(self.questions.currentRow())

  @QtCore.Slot()
  def add_answer(self):
    text: str = self.answer_textbox.text()
    if text:
      self.answers.addItem(text)
      self.answer_textbox.clear()

  @QtCore.Slot()
  def remove_answer(self):
    self.answers.takeItem(self.questions.currentRow())

  @QtCore.Slot()
  def send_questions(self):
    def callback(data):
      if data['status'] != 'ok':
        print(data)
      else:
        self.answer_textbox.setEnabled(False)
        self.question_textbox.setEnabled(False)
        self.send_button.setEnabled(False)

    questions = [self.questions.item(i).text()
                 for i in range(self.questions.count())]
    answers = [self.answers.item(i). text()
               for i in range(self.answers.count())]
    if (len(questions) >= self.min_questions and
        len(answers) >= self.min_answers):
      sio.emit(
        "add-questions",
        (room_code, questions, answers),
        callback=callback
      )


class QuestionWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    layout = QtWidgets.QVBoxLayout()
    self.setLayout(layout)

    self.question_label = QtWidgets.QLabel()
    layout.addWidget(self.question_label)
    self.players_list = QtWidgets.QListWidget()
    layout.addWidget(self.players_list)
    self.vote_button = QtWidgets.QPushButton("Vote")
    self.vote_button.clicked.connect(self.cast_vote)
    layout.addWidget(self.vote_button)

  def initialize(self, question, players):
    self.question_label.setText(question)
    self.players_list.clear()
    for player in players:
      if player['id'] != sio.get_sid():
        self.add_player(player['id'], player['username'])

  def add_player(self, user_id, username):
    icon = QtGui.QIcon.fromTheme("emblem-question")
    item = QtWidgets.QListWidgetItem(icon, username)
    item.user_id = user_id
    self.players_list.addItem(item)

  def set_player_done(self, user_id):
    item = next(self.players_list.item(i)
                for i in range(self.players_list.count())
                if self.players_list.item(i).user_id == user_id)
    item.setIcon(QtGui.QIcon.fromTheme("emblem-checked"))

  @QtCore.Slot()
  def cast_vote(self):
    def callback(data):
      if data['status'] != 'ok':
        return print(data)
    item = self.players_list.currentItem()
    sio.emit('cast-vote', (room_code, item.user_id), callback=callback)
    

class AnswerWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    layout = QtWidgets.QVBoxLayout()
    self.setLayout(layout)

    layout.addStretch(1)
    self.question_label = QtWidgets.QLabel()
    layout.addWidget(self.question_label)
    self.answer_label = QtWidgets.QLabel()
    layout.addWidget(self.answer_label)
    self.done_button = QtWidgets.QPushButton("Done")
    self.done_button.clicked.connect(self.finish_presentation)
    layout.addStretch(1)
    layout.addWidget(self.done_button)

  def initialize(self, question, answer):
    self.question_label.setText(question)
    self.answer_label.setText(answer)
    self.done_button.setEnabled(True)

  @QtCore.Slot()
  def finish_presentation(self):
    self.done_button.setEnabled(False)
    sio.emit('finish-presentation', (room_code,))


class GameOverWidget(QtWidgets.QWidget):
  def __init__(self):
    QtWidgets.QWidget.__init__(self)
    layout = QtWidgets.QVBoxLayout()
    self.setLayout(layout)

    layout.addStretch(1)
    layout.addWidget(QLabel("Game over"))
    layout.addStretch(1)
    return_button = QPushButton("Return to lobby")
    return_button.clicked.connect(self.return_to_lobby)
    layout.addWidget(return_button)

  @QtCore.Slot()
  def return_to_lobby(self):
    window_layout.setCurrentWidget(lobby_widget)


room_code = ""
app = QtWidgets.QApplication(sys.argv)
window = QtWidgets.QWidget()
window_layout = QtWidgets.QStackedLayout()
window.setLayout(window_layout)

login_widget = LoginWidget()
window_layout.addWidget(login_widget)
lobby_widget = LobbyWidget()
window_layout.addWidget(lobby_widget)
preparation_widget = PreparationWidget()
window_layout.addWidget(preparation_widget)
question_widget = QuestionWidget()
window_layout.addWidget(question_widget)
answer_widget = AnswerWidget()
window_layout.addWidget(answer_widget)
game_over_widget = GameOverWidget()
window_layout.addWidget(game_over_widget)


@sio.on('player-joined')
def on_player_joined(data):
  lobby_widget.add_player(data['id'], data['username'])

@sio.on('preparation-started')
def on_preparation_started(data):
  preparation_widget.set_num_players(len(data['players']))
  window_layout.setCurrentWidget(preparation_widget)

@sio.on('turn-started')
def on_turn_started(data):
  if data['currentPlayer'] == sio.get_sid():
    question_widget.initialize(data['question'], data['players'])
    window_layout.setCurrentWidget(question_widget)
  else:
    answer_widget.initialize(data['question'], data["answer"])
    window_layout.setCurrentWidget(answer_widget)

@sio.on('presentation-done')
def on_presentation_done(data):
  question_widget.set_player_done(data)

@sio.on('game-over')
def on_game_over(data):
  window_layout.setCurrentWidget(game_over_widget)


if __name__ == "__main__":
  window.resize(400, 300)
  window.show()
  exit_code = app.exec_()
  sio.disconnect()
  sys.exit(exit_code)
