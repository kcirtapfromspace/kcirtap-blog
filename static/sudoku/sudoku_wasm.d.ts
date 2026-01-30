/* tslint:disable */
/* eslint-disable */

/**
 * The main WASM game controller
 */
export class SudokuGame {
    free(): void;
    [Symbol.dispose](): void;
    /**
     * Get current difficulty
     */
    difficulty(): string;
    /**
     * Get elapsed time in seconds
     */
    elapsed_secs(): number;
    /**
     * Get formatted elapsed time
     */
    elapsed_string(): string;
    /**
     * Get current height
     */
    get_height(): number;
    /**
     * Get current game state as JSON
     */
    get_state_json(): string;
    /**
     * Get current width
     */
    get_width(): number;
    /**
     * Handle keyboard input
     */
    handle_key(event: KeyboardEvent): boolean;
    /**
     * Get number of hints used
     */
    hints_used(): number;
    /**
     * Check if game is complete
     */
    is_complete(): boolean;
    /**
     * Check if game is over (too many mistakes)
     */
    is_game_over(): boolean;
    /**
     * Check if paused
     */
    is_paused(): boolean;
    /**
     * Load game state from JSON
     */
    load_state_json(json: string): boolean;
    /**
     * Get number of mistakes
     */
    mistakes(): number;
    /**
     * Create a new game attached to a canvas element
     */
    constructor(canvas_id: string);
    /**
     * Start a new game with specified difficulty
     */
    new_game(difficulty: string): void;
    /**
     * Resize the game canvas
     */
    resize(width: number, height: number): void;
    /**
     * Set the color theme
     */
    set_theme(theme_name: string): void;
    /**
     * Update game state (call from requestAnimationFrame)
     */
    tick(): void;
    /**
     * Toggle pause
     */
    toggle_pause(): void;
}

export function init(): void;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_sudokugame_free: (a: number, b: number) => void;
    readonly sudokugame_difficulty: (a: number) => [number, number];
    readonly sudokugame_elapsed_secs: (a: number) => number;
    readonly sudokugame_elapsed_string: (a: number) => [number, number];
    readonly sudokugame_get_height: (a: number) => number;
    readonly sudokugame_get_state_json: (a: number) => [number, number];
    readonly sudokugame_get_width: (a: number) => number;
    readonly sudokugame_handle_key: (a: number, b: any) => number;
    readonly sudokugame_hints_used: (a: number) => number;
    readonly sudokugame_is_complete: (a: number) => number;
    readonly sudokugame_is_game_over: (a: number) => number;
    readonly sudokugame_is_paused: (a: number) => number;
    readonly sudokugame_load_state_json: (a: number, b: number, c: number) => number;
    readonly sudokugame_mistakes: (a: number) => number;
    readonly sudokugame_new: (a: number, b: number) => [number, number, number];
    readonly sudokugame_new_game: (a: number, b: number, c: number) => void;
    readonly sudokugame_resize: (a: number, b: number, c: number) => void;
    readonly sudokugame_set_theme: (a: number, b: number, c: number) => void;
    readonly sudokugame_tick: (a: number) => void;
    readonly sudokugame_toggle_pause: (a: number) => void;
    readonly init: () => void;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
