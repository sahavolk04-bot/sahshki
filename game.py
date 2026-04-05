from copy import deepcopy

EMPTY = 0
BLACK = 1       # ⚫ (ходит первым)
WHITE = 2       # ⚪
BLACK_KING = 3  # 🔱
WHITE_KING = 4  # 👑


class CheckersGame:
    def __init__(self, black_id: int, black_name: str, white_id: int, white_name: str):
        self.black_id = black_id
        self.black_name = black_name
        self.white_id = white_id
        self.white_name = white_name
        self.current_turn = BLACK
        self.selected = None
        self.message_id = None
        self.chat_id = None
        self.board = self._init_board()
        # Track if a capture chain is in progress
        self.must_capture_from = None

    def _init_board(self):
        board = [[EMPTY] * 8 for _ in range(8)]
        # Place black pieces (rows 0-2, dark squares)
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:
                    board[row][col] = BLACK
        # Place white pieces (rows 5-7, dark squares)
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    board[row][col] = WHITE
        return board

    def _is_black(self, cell):
        return cell in (BLACK, BLACK_KING)

    def _is_white(self, cell):
        return cell in (WHITE, WHITE_KING)

    def _is_king(self, cell):
        return cell in (BLACK_KING, WHITE_KING)

    def _is_enemy(self, cell, turn):
        if turn == BLACK:
            return self._is_white(cell)
        return self._is_black(cell)

    def get_all_captures(self, turn):
        """Return all pieces of 'turn' that can capture."""
        pieces = []
        for r in range(8):
            for c in range(8):
                cell = self.board[r][c]
                if (turn == BLACK and self._is_black(cell)) or \
                   (turn == WHITE and self._is_white(cell)):
                    if self._get_captures(r, c):
                        pieces.append((r, c))
        return pieces

    def _get_captures(self, row, col):
        """Return list of landing squares for captures from (row, col)."""
        cell = self.board[row][col]
        captures = []
        dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        if self._is_king(cell):
            # Kings can capture in all 4 diagonal directions (fly over empty)
            for dr, dc in dirs:
                r, c = row + dr, col + dc
                found_enemy = False
                while 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if found_enemy:
                        if target == EMPTY:
                            captures.append((r, c))
                        else:
                            break
                    else:
                        if self._is_enemy(target, BLACK if self._is_black(cell) else WHITE):
                            found_enemy = True
                        elif target != EMPTY:
                            break
                    r += dr
                    c += dc
        else:
            # Normal piece captures in all 4 directions (jump over adjacent)
            for dr, dc in dirs:
                mid_r, mid_c = row + dr, col + dc
                land_r, land_c = row + 2*dr, col + 2*dc
                if 0 <= land_r < 8 and 0 <= land_c < 8:
                    mid = self.board[mid_r][mid_c]
                    land = self.board[land_r][land_c]
                    turn = BLACK if self._is_black(cell) else WHITE
                    if self._is_enemy(mid, turn) and land == EMPTY:
                        captures.append((land_r, land_c))

        return captures

    def _get_moves(self, row, col):
        """Return list of squares a piece can move to (no capture)."""
        cell = self.board[row][col]
        moves = []

        if self._is_king(cell):
            dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            for dr, dc in dirs:
                r, c = row + dr, col + dc
                while 0 <= r < 8 and 0 <= c < 8 and self.board[r][c] == EMPTY:
                    moves.append((r, c))
                    r += dr
                    c += dc
        else:
            # Black moves down (row increases), white moves up (row decreases)
            forward = 1 if self._is_black(cell) else -1
            for dc in (-1, 1):
                r, c = row + forward, col + dc
                if 0 <= r < 8 and 0 <= c < 8 and self.board[r][c] == EMPTY:
                    moves.append((r, c))

        return moves

    def get_valid_moves_for_piece(self, row, col) -> list:
        """
        Returns valid destination squares for piece at (row, col).
        Captures are mandatory; if any piece can capture, only captures shown.
        """
        cell = self.board[row][col]
        if cell == EMPTY:
            return []

        # Determine turn based on cell
        turn = BLACK if self._is_black(cell) else WHITE

        # If a capture chain is active and this isn't that piece
        if self.must_capture_from and self.must_capture_from != (row, col):
            return []

        # Check if any piece of this side must capture
        must_capture_pieces = self.get_all_captures(turn)

        if must_capture_pieces:
            if (row, col) in must_capture_pieces:
                return self._get_captures(row, col)
            return []
        else:
            return self._get_moves(row, col)

    def make_move(self, from_pos: tuple, to_pos: tuple) -> dict:
        """
        Execute a move. Returns dict with info about what happened.
        """
        fr, fc = from_pos
        tr, tc = to_pos
        cell = self.board[fr][fc]

        result = {"captured": False, "must_continue": False}

        # Move the piece
        self.board[tr][tc] = cell
        self.board[fr][fc] = EMPTY

        # Check if this was a capture
        dr = tr - fr
        dc = tc - fc

        captured = False
        if self._is_king(cell):
            # King capture: find enemy between from and to
            step_r = 1 if dr > 0 else -1
            step_c = 1 if dc > 0 else -1
            r, c = fr + step_r, fc + step_c
            while (r, c) != (tr, tc):
                if self.board[r][c] != EMPTY:
                    self.board[r][c] = EMPTY
                    captured = True
                    break
                r += step_r
                c += step_c
        else:
            if abs(dr) == 2:
                mid_r = (fr + tr) // 2
                mid_c = (fc + tc) // 2
                if self.board[mid_r][mid_c] != EMPTY:
                    self.board[mid_r][mid_c] = EMPTY
                    captured = True

        result["captured"] = captured

        # Promote to king
        if cell == BLACK and tr == 7:
            self.board[tr][tc] = BLACK_KING
        elif cell == WHITE and tr == 0:
            self.board[tr][tc] = WHITE_KING

        # Check if must continue capturing (multi-jump)
        if captured:
            next_captures = self._get_captures(tr, tc)
            if next_captures:
                self.must_capture_from = (tr, tc)
                result["must_continue"] = True
                return result

        # Switch turn
        self.must_capture_from = None
        self.current_turn = WHITE if self.current_turn == BLACK else BLACK
        return result

    def check_winner(self):
        """Returns BLACK, WHITE, or None."""
        black_pieces = [(r, c) for r in range(8) for c in range(8)
                        if self._is_black(self.board[r][c])]
        white_pieces = [(r, c) for r in range(8) for c in range(8)
                        if self._is_white(self.board[r][c])]

        if not black_pieces:
            return WHITE
        if not white_pieces:
            return BLACK

        # Check if current player has no moves
        turn = self.current_turn
        pieces = black_pieces if turn == BLACK else white_pieces

        for r, c in pieces:
            if self.get_valid_moves_for_piece(r, c):
                return None

        # No moves available — opponent wins
        return WHITE if turn == BLACK else BLACK
