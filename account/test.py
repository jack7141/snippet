from collections import deque


def solution(r, delivery):
    grid = [delivery[i:i + r] for i in range(0, len(delivery), r)]
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    max_tips = 0

    def dfs(row, col, current_time, current_tips):
        nonlocal max_tips
        if current_time > grid[row][col][0]:
            return
        current_tips += grid[row][col][1]
        max_tips = max(max_tips, current_tips)

        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < r and 0 <= new_col < r:
                dfs(new_row, new_col, current_time + 1, current_tips)

    dfs(0, 0, 0, 0)

    return max_tips


# Test cases
# Example 1
# r1, delivery1 = 3, [[1, 5], [8, 3], [4, 2], [2, 3], [3, 1], [3, 2], [4, 2], [5, 2], [4, 1]]
# result1 = solution(r1, delivery1)
# assert result1 == 17, f"Expected 17, got {result1}"

# Example 2
r2, delivery2 = 4, [[1, 10], [8, 1], [8, 1], [3, 100], [8, 1], [8, 1], [8, 1], [8, 1],
                    [8, 1], [8, 1], [8, 1], [8, 1], [9, 100], [8, 1], [8, 1], [8, 1]]
result2 = solution(r2, delivery2)
assert result2 == 217, f"Expected 217, got {result2}"