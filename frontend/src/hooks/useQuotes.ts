import { useEffect, useState } from "react";

import {
  getBatchQuotes,
  getQuote,
  type BatchQuoteRequestItem,
  type BatchQuoteResponse,
  type QuoteResponse,
} from "../lib/api";

type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

function createInitialState<T>(): AsyncState<T> {
  return { data: null, loading: true, error: null };
}

export function useQuote(request: BatchQuoteRequestItem) {
  const [state, setState] = useState<AsyncState<QuoteResponse>>(createInitialState);

  useEffect(() => {
    let isMounted = true;
    setState(createInitialState());
    getQuote(request)
      .then((data) => {
        if (isMounted) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setState({ data: null, loading: false, error: error instanceof Error ? error.message : "Unknown error" });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [request.exchange, request.expiry_date, request.product_type, request.right, request.strike_price, request.symbol]);

  return state;
}

export function useBatchQuotes(requests: BatchQuoteRequestItem[]) {
  const [state, setState] = useState<AsyncState<BatchQuoteResponse>>(createInitialState);

  useEffect(() => {
    let isMounted = true;
    setState(createInitialState());
    getBatchQuotes(requests)
      .then((data) => {
        if (isMounted) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setState({ data: null, loading: false, error: error instanceof Error ? error.message : "Unknown error" });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [JSON.stringify(requests)]);

  return state;
}
