export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function createInitialState<T>(): AsyncState<T> {
  return { data: null, loading: true, error: null };
}
