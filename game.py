from copy import deepcopy
 
EMPTY = 0
BLACK = 1
WHITE = 2
BLACK_KING = 3
WHITE_KING = 4
 
 
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
        self.must_capture_from = None
 
    def _init_board(self):
        board = [[EMPTY] * 8 for _ in range(8)]
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:
                    board[row][col] = BLACK
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
 
    def _owner(self, cell):
        if self._is_black(cell):
            return BLACK
        if self._is_white(cell):
            return WHITE
        return None
 
    def _is_enemy(self, cell, turn):
        if turn == BLACK:
            return self._is_white(cell)
        return self._is_black(cell)
 
    def _get_captures(self, row, col):
        cell = self.board[row][col]
        if cell == EMPTY:
            return []
        turn = self._owner(cell)
        captures = []
        dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
 
        if self._is_king(cell):
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
                        if self._is_enemy(target, turn):
                            found_enemy = True
                        elif target != EMPTY:
                            break
                    r += dr
                    c += dc
        else:
            for dr, dc in dirs:
                mid_r, mid_c = row + dr, col + dc
                land_r, land_c = row + 2 * dr, col + 2 * dc
                if not (0 <= mid_r < 8 and 0 <= mid_c < 8):
                    continue
                if not (0 <= land_r < 8 and 0 <= land_c < 8):
                    continue
                mid = self.board[mid_r][mid_c]
                land = self.board[land_r][land_c]
                if self._is_enemy(mid, turn) and land == EMPTY:
                    captures.append((land_r, land_c))
 
        return captures
 
    def _get_moves(self, row, col):
        cell = self.board[row][col]
        if cell == EMPTY:
            return []
        moves = []
        if self._is_king(cell):
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                r, c = row + dr, col + dc
                while 0 <= r < 8 and 0 <= c < 8 and self.board[r][c] == EMPTY:
                    moves.append((r, c))
                    r += dr
                    c += dc
        else:
            forward = 1 if self._is_black(cell) else -1
            for dc in (-1, 1):
                r, c = row + forward, col + dc
                if 0 <= r < 8 and 0 <= c < 8 and self.board[r][c] == EMPTY:
                    moves.append((r, c))
        return moves
 
    def get_all_captures_for_turn(self, turn):
        pieces = []
        for r in range(8):
            for c in range(8):
                cell = self.board[r][c]
                if self._owner(cell) == turn:
                    if self._get_captures(r, c):
                        pieces.append((r, c))
        return pieces
 
    def get_valid_moves_for_piece(self, row, col) -> list:
        cell = self.board[row][col]
        if cell == EMPTY:
            return []
        turn = self._owner(cell)
 
        if self.must_capture_from is not None:
            if self.must_capture_from != (row, col):
                return []
            return self._get_captures(row, col)
 
        must_capture = self.get_all_captures_for_turn(turn)
        if must_capture:
            if (row, col) in must_capture:
                return self._get_captures(row, col)
            return []
 
        return self._get_moves(row, col)
 
    def make_move(self, from_pos: tuple, to_pos: tuple) -> dict:
        fr, fc = from_pos
        tr, tc = to_pos
        cell = self.board[fr][fc]
        result = {"captured": False, "must_continue": False}
 
        self.board[tr][tc] = cell
        self.board[fr][fc] = EMPTY
 
        captured = False
        dr = tr - fr
        dc = tc - fc
 
        if self._is_king(cell):
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
 
        promoted = False
        if cell == BLACK and tr == 7:
            self.board[tr][tc] = BLACK_KING
            promoted = True
        elif cell == WHITE and tr == 0:
            self.board[tr][tc] = WHITE_KING
            promoted = True
 
        if captured and not promoted:
            next_captures = self._get_captures(tr, tc)
            if next_captures:
                self.must_capture_from = (tr, tc)
                result["must_continue"] = True
                return result
 
        self.must_capture_from = None
        self.current_turn = WHITE if self.current_turn == BLACK else BLACK
        return result
 
    def check_winner(self):
        black_pieces = []
        white_pieces = []
        for r in range(8):
            for c in range(8):
                cell = self.board[r][c]
                if self._is_black(cell):
                    black_pieces.append((r, c))
                elif self._is_white(cell):
                    white_pieces.append((r, c))
 
        if not black_pieces:
            return WHITE
        if not white_pieces:
            return BLACK
 
        for r, c in (black_pieces if self.current_turn == BLACK else white_pieces):
            if self.get_valid_moves_for_piece(r, c):
                return None
 
        return WHITE if self.current_turn == BLACK else BLACK
