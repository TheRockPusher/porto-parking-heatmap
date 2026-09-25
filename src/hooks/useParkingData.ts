import { useCallback, useEffect, useState } from "react";
import type { ParkingData } from "../types";

export function useParkingData() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    data: ParkingData | null;
    loading: boolean;
    error: string | null;
  }>({ data: null, loading: true, error: null });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const response = await fetch(
          `${import.meta.env.BASE_URL}data/porto-parking.json`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error(`Snapshot request returned HTTP ${response.status}.`);
        const data: ParkingData = await response.json();
        if (
          data.schemaVersion !== 1 ||
          !Array.isArray(data.sources) ||
          !["streets", "zones", "spaces", "garages"].every((kind) => {
            const collection = data.collections?.[kind as keyof ParkingData["collections"]];
            return collection?.type === "FeatureCollection" && Array.isArray(collection.features);
          })
        ) {
          throw new Error("The parking snapshot has an unsupported format.");
        }
        if (!controller.signal.aborted) setState({ data, loading: false, error: null });
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            data: null,
            loading: false,
            error: error instanceof Error ? error.message : "The parking snapshot could not be read.",
          });
        }
      }
    }

    void load();
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ data: null, loading: true, error: null });
    setAttempt((value) => value + 1);
  }, []);

  return { ...state, retry };
}
