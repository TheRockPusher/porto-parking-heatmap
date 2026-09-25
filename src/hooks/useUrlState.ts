import { useEffect, useState } from "react";
import { DEFAULT_STATE, LAYER_KINDS, SPACE_STATUSES } from "../lib/parking";
import type { ExplorerState } from "../types";

function readUrlState(): ExplorerState {
  const params = new URLSearchParams(window.location.search);
  const layerValues = params.get("layers")?.split(",");
  const statusValues = params.get("status")?.split(",");
  const feature = params.get("feature");
  return {
    layers: params.get("layers") === "none" ? [] :
      layerValues?.length && layerValues.every((value) => LAYER_KINDS.some((kind) => kind === value))
        ? LAYER_KINDS.filter((kind) => layerValues.includes(kind)) : DEFAULT_STATE.layers,
    statuses: params.get("status") === "none" ? [] :
      statusValues?.length && statusValues.every((value) => SPACE_STATUSES.some((status) => status === value))
        ? SPACE_STATUSES.filter((status) => statusValues.includes(status)) : DEFAULT_STATE.statuses,
    selectedId: feature && /^(streets|zones|spaces|garages):[\w-]{1,100}$/.test(feature) ? feature : null,
  };
}

export function useUrlState() {
  const [state, setState] = useState<ExplorerState>(readUrlState);

  useEffect(() => {
    const onPopState = () => setState(readUrlState());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.search = "";
    url.hash = "";
    url.searchParams.set("layers", state.layers.join(",") || "none");
    url.searchParams.set("status", state.statuses.join(",") || "none");
    if (state.selectedId) url.searchParams.set("feature", state.selectedId);
    window.history.replaceState(null, "", url);
  }, [state]);

  return [state, setState] as const;
}
