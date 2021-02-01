"use strict";

const server = require("http").createServer();
const io = require('socket.io')(server);


const sizeof = function (obj) {
  return Object.keys(obj).length
}
const shuffle = function(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    let j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}


function newGameRoom(owner) {
  let roomcode = [];
  for (let i = 0; i < 6; i++) {
    roomcode.push((Math.floor(Math.random() * 26 + 10)).toString(36));
  }
  return {
    code: roomcode.join("").toUpperCase(),
    host: owner,
    readyPlayers: 0,
    players: [],
    state: "lobby",
    questions: [],
    answers: []
  };
}

function restartGame(room) {
  room.state = "lobby";
  room.readyPlayers = 0;
  room.questions = [];
  room.answers = [];
}

function initGame(room) {
  room.state = "game";
  shuffle(room.questions);
  shuffle(room.answers);
  room.playersQueue = room.players.slice();
  shuffle(room.playersQueue);
}

/* start a new turn and return true if the game is done */
function nextTurn(room) {
  room.readyPlayers = 0;
  if (room.questions.length == 0 || room.answers.length < room.players.length) {
    finalizeGame(room);
    return true;
  }
  let question = room.questions.pop();
  let currentPlayer = room.playersQueue.pop();
  room.playersQueue.unshift(currentPlayer);
  for (let i in room.playersQueue) {
    let player = room.playersQueue[i];
    let answer = null;
    if (i > 0) {
      answer = room.answers.pop();
    }
    io.to(player.id).emit("turn-started", {
      question: question,
      answer: answer,
      currentPlayer: currentPlayer.id,
      players: room.players
    });
  }
  return false;
}

function finalizeGame(room) {
  console.log(`Game in room ${room.code} finished.`);
  restartGame(room);
  io.to(room.code).emit("game-over", null);
}

var gameRooms = {}

io.on('connection', (socket) => {
  console.log("new connection " + socket.id);

  socket.on("disconnect", () => {
    console.log(socket.id + " disconnected");
  })

  socket.on("join-room", (roomcode, username, callback) => {
    let room;
    if (!roomcode) {
      room = newGameRoom(socket.id);
      gameRooms[room.code] = room;
    }
    else {
      room = gameRooms[roomcode];
    }
    if (room == undefined) {
      callback({ status: "error", reason: "no-such-room" });
    }
    else if (room.state != 'lobby') {
      callback({ status: "error", reason: "game-in-progress"})
    }
    else {
      socket.join(room.code);
      room.players.push({ id: socket.id, username: username });
      console.log(`Player ${username} joined ${room.code}`);
      callback({ 
        status: "ok",
        roomcode: room.code,
        players: room.players,
        host: room.host
      });
      socket.to(room.code).emit("player-joined", {id: socket.id, username: username})
    }
  });

  socket.on("start-game", (roomcode, callback) => {
    let room = gameRooms[roomcode];
    if (room == undefined) {
      callback({ status: "error", reason: "no-such-room" });
    }
    else if (sizeof(room.players) < 3) {
      callback({ status: "error", reason: "not-enough-players" });
    }
    else if (room.state != "lobby") {
      callback({ status: "error", reason: "illegal-state" });
    }
    else if (room.host != socket.id) {
      callback({ status: "error", reason: "not-an-owner" });
    }
    else {
      room.state = "preparation";
      callback({ status: 'ok' });
      io.to(room.code).emit("preparation-started", {players: room.players});
    }
  })

  socket.on("add-questions", (roomcode, questions, answers, callback) => {
    let room = gameRooms[roomcode];
    if (room == undefined) {
      callback({ status: "error", reason: "no-such-room" });
    }
    else if (room.state != "preparation") {
      callback({ status: "error", reason: "illegal-state" })
    }
    else {
      for (let q of questions) {
        room.questions.push(q);
      }
      for (let a of answers) {
        room.answers.push(a);
      }
      callback({ status: "ok" });
      socket.to(room.code).emit("player-ready", socket.id);
      if (sizeof(room.players) == ++room.readyPlayers) {
        initGame(room);
        nextTurn(room);
      }
    }
  });

  socket.on("finish-presentation", (roomcode) => {
    let room = gameRooms[roomcode];
    if (room == undefined) {}
    else {
      console.log(`Player ${socket.id} finished presentation`);
      socket.to(room.code).emit("presentation-done", socket.id);
      if (sizeof(room.players) - 1 == ++room.readyPlayers) {
        io.to(room.code).emit("voting-phase", {
          currentPlayer: room.playersQueue[0]
        });
      }
    }
  });

  socket.on("cast-vote", (roomcode, playerid, callback) => {
    let room = gameRooms[roomcode];
    if (room == undefined) {}
    else if (room.playersQueue[0].id != socket.id) {
      callback({ status: "error", reason: "not-your-turn" });
    }
    else {
      console.log(`Player ${socket.id} voted on ${playerid}`);
      callback({ status: "ok" })
      io.to(room.code).emit("player-voted", playerid);
      nextTurn(room);
    }
  })
})

const PORT = process.env.PORT || 4000
console.log(`sever starts listening on port ${PORT}`);
server.listen(PORT);
