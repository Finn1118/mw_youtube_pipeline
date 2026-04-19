const graphSvg = d3.select("#graph");
const emptyState = document.getElementById("emptyState");
const detailContent = document.getElementById("detailContent");
const statusText = document.getElementById("statusText");
const analyzeForm = document.getElementById("analyzeForm");
const urlInput = document.getElementById("urlInput");
const analyzeButton = document.getElementById("analyzeButton");
const toast = document.getElementById("toast");

const svgNode = graphSvg.node();
const width = () => svgNode.clientWidth || 1200;
const height = () => svgNode.clientHeight || 800;

let simulation = null;
let zoomLayer = null;
let linkLayer = null;
let nodeLayer = null;
let labelLayer = null;
let nodes = [];
let links = [];
let previousNodeIds = new Set();

const tooltip = d3
  .select("body")
  .append("div")
  .attr("class", "graph-tooltip hidden")
  .style("position", "fixed");

function showToast(message, isError = false) {
  toast.classList.remove("hidden");
  toast.textContent = message;
  toast.classList.toggle("toast-error", isError);
  window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 4000);
}

function setStatus(message) {
  statusText.textContent = message;
}

function formatDuration(totalSeconds) {
  const rounded = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const minutes = Math.floor(rounded / 60);
  const seconds = String(rounded % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function buildGraphData(videos) {
  const builtNodes = [];
  const builtLinks = [];

  videos.forEach((video) => {
    const videoId = `video:${video.video_id}`;
    builtNodes.push({
      id: videoId,
      kind: "video",
      radius: 38,
      title: video.title || video.video_id,
      video,
      thumbnail: video.thumbnail || "",
      cluster: video.video_id,
    });

    (video.speakers || []).forEach((speaker, idx) => {
      const personId = `video:${video.video_id}:speaker:${speaker.speaker_id ?? idx}`;
      builtNodes.push({
        id: personId,
        kind: "person",
        radius: 22,
        name: speaker.name || "Unknown",
        speaker,
        video,
        cluster: video.video_id,
      });
      builtLinks.push({
        source: personId,
        target: videoId,
      });
    });
  });

  return { nodes: builtNodes, links: builtLinks };
}

function initSvg() {
  graphSvg.selectAll("*").remove();
  graphSvg.attr("viewBox", `0 0 ${width()} ${height()}`);
  zoomLayer = graphSvg.append("g").attr("class", "zoom-layer");
  linkLayer = zoomLayer.append("g").attr("class", "links");
  nodeLayer = zoomLayer.append("g").attr("class", "nodes");
  labelLayer = zoomLayer.append("g").attr("class", "labels");

  graphSvg.call(
    d3
      .zoom()
      .scaleExtent([0.35, 2.5])
      .on("zoom", (event) => {
        zoomLayer.attr("transform", event.transform);
      })
  );
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function patchSpeakerNames(videoId, renames) {
  const response = await fetch(`/library/${encodeURIComponent(videoId)}/speakers`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ renames }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Rename failed (${response.status})`);
  }
  return response.json();
}

async function renameSpeaker(videoId, speakerId, currentName) {
  const next = window.prompt("Rename speaker", currentName || "");
  if (next === null) return;
  const trimmed = next.trim();
  if (!trimmed || trimmed === currentName) return;
  try {
    await patchSpeakerNames(videoId, [{ speaker_id: Number(speakerId), name: trimmed }]);
    showToast("Speaker renamed.");
    await refreshGraph();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "Rename failed.", true);
  }
}

async function swapSpeakerNames(video) {
  const speakers = video.speakers || [];
  if (speakers.length < 2) {
    showToast("Need at least two speakers to swap.", true);
    return;
  }
  let a = speakers[0];
  let b = speakers[1];
  if (speakers.length > 2) {
    const pick = window.prompt(
      "Swap which two speaker ids? (comma separated, e.g. 0,1)",
      `${speakers[0].speaker_id},${speakers[1].speaker_id}`
    );
    if (!pick) return;
    const ids = pick.split(",").map((value) => Number(value.trim()));
    a = speakers.find((s) => s.speaker_id === ids[0]);
    b = speakers.find((s) => s.speaker_id === ids[1]);
    if (!a || !b) {
      showToast("Could not find those speaker ids.", true);
      return;
    }
  }
  try {
    await patchSpeakerNames(video.video_id, [
      { speaker_id: Number(a.speaker_id), name: b.name },
      { speaker_id: Number(b.speaker_id), name: a.name },
    ]);
    showToast(`Swapped "${a.name}" and "${b.name}".`);
    await refreshGraph();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "Swap failed.", true);
  }
}

function updateDetails(node) {
  if (!node) {
    detailContent.innerHTML = "Select a person or video node to inspect details.";
    return;
  }

  if (node.kind === "video") {
    const video = node.video;
    const speakerItems = (video.speakers || [])
      .map(
        (speaker) => `
          <li class="rounded-md border border-slate-700 bg-slate-950/50 p-2">
            <div class="flex items-center justify-between gap-2">
              <p class="font-medium text-slate-200">${escapeHtml(speaker.name || "Unknown speaker")}</p>
              <button
                type="button"
                class="rounded border border-slate-600 bg-slate-800 px-2 py-0.5 text-xs text-slate-200 hover:bg-slate-700"
                data-action="rename"
                data-video-id="${escapeHtml(video.video_id)}"
                data-speaker-id="${escapeHtml(speaker.speaker_id)}"
                data-current-name="${escapeHtml(speaker.name || "")}"
              >Rename</button>
            </div>
            <p class="text-xs text-slate-400">${speaker.word_count || 0} words &bull; ${formatDuration(
              speaker.duration_seconds
            )}</p>
            <p class="mt-1 text-xs text-slate-300">${escapeHtml(speaker.preview || "")}</p>
          </li>
        `
      )
      .join("");

    const swapButton =
      (video.speakers || []).length >= 2
        ? `<button type="button" class="rounded border border-sky-600 bg-sky-900/40 px-2 py-1 text-xs text-sky-100 hover:bg-sky-800" data-action="swap" data-video-id="${escapeHtml(
            video.video_id
          )}">Swap speaker labels</button>`
        : "";

    detailContent.innerHTML = `
      <article class="space-y-3">
        <img src="${escapeHtml(video.thumbnail)}" alt="" class="h-40 w-full rounded-md object-cover" />
        <h3 class="text-base font-semibold text-slate-100">${escapeHtml(video.title)}</h3>
        <p class="text-xs text-slate-400">${escapeHtml(video.uploader || "")}</p>
        <p class="text-xs text-slate-400">Duration: ${formatDuration(video.duration_seconds)}</p>
        <div class="flex items-center justify-between">
          <p class="text-xs text-slate-400">Speakers: ${(video.speakers || []).length}</p>
          ${swapButton}
        </div>
        <ul class="space-y-2">${speakerItems || "<li>No speaker cards.</li>"}</ul>
      </article>
    `;
    return;
  }

  const speaker = node.speaker || {};
  const video = node.video || {};
  const displayName = speaker.name && speaker.name !== "Unknown" ? speaker.name : "Unknown speaker";
  detailContent.innerHTML = `
    <article class="space-y-3">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-base font-semibold text-slate-100">${escapeHtml(displayName)}</h3>
        <button
          type="button"
          class="rounded border border-slate-600 bg-slate-800 px-2 py-0.5 text-xs text-slate-200 hover:bg-slate-700"
          data-action="rename"
          data-video-id="${escapeHtml(video.video_id || "")}"
          data-speaker-id="${escapeHtml(speaker.speaker_id)}"
          data-current-name="${escapeHtml(speaker.name || "")}"
        >Rename</button>
      </div>
      <p class="text-xs text-slate-400">${escapeHtml(video.title || "")}</p>
      <p class="text-xs text-slate-400">${speaker.word_count || 0} words &bull; ${formatDuration(
        speaker.duration_seconds
      )}</p>
      <div class="rounded-md border border-slate-700 bg-slate-950/50 p-3">
        <p class="text-xs uppercase tracking-wide text-slate-400">Preview</p>
        <p class="mt-1 text-sm text-slate-200">${escapeHtml(speaker.preview || "")}</p>
      </div>
      <div class="rounded-md border border-slate-700 bg-slate-950/50 p-3">
        <p class="text-xs uppercase tracking-wide text-slate-400">Full transcript</p>
        <p class="mt-1 max-h-72 overflow-y-auto whitespace-pre-wrap text-sm text-slate-200">${escapeHtml(
          speaker.full_text || ""
        )}</p>
      </div>
    </article>
  `;
}

detailContent.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const action = target.dataset?.action;
  if (action === "rename") {
    renameSpeaker(target.dataset.videoId, target.dataset.speakerId, target.dataset.currentName);
  } else if (action === "swap") {
    const videoId = target.dataset.videoId;
    const match = (window.__libraryCache || []).find((video) => video.video_id === videoId);
    if (match) swapSpeakerNames(match);
  }
});

function renderGraph(data) {
  nodes = data.nodes.map((node) => ({ ...node }));
  links = data.links.map((link) => ({ ...link }));
  const hasData = nodes.length > 0;
  emptyState.style.display = hasData ? "none" : "grid";

  if (!hasData) {
    if (simulation) {
      simulation.stop();
    }
    linkLayer.selectAll("*").remove();
    nodeLayer.selectAll("*").remove();
    labelLayer.selectAll("*").remove();
    updateDetails(null);
    return;
  }

  const clusterCenters = new Map();
  nodes.forEach((node) => {
    if (!clusterCenters.has(node.cluster)) {
      const angle = clusterCenters.size * 1.3;
      clusterCenters.set(node.cluster, {
        x: width() / 2 + Math.cos(angle) * 180,
        y: height() / 2 + Math.sin(angle) * 140,
      });
    }
    const center = clusterCenters.get(node.cluster);
    const isNew = !previousNodeIds.has(node.id);
    if (isNew) {
      node.x = width() / 2;
      node.y = height() / 2;
      node.vx = (Math.random() - 0.5) * 12;
      node.vy = (Math.random() - 0.5) * 12;
    } else {
      node.x = center.x + (Math.random() - 0.5) * 24;
      node.y = center.y + (Math.random() - 0.5) * 24;
    }
  });

  previousNodeIds = new Set(nodes.map((node) => node.id));

  const linkSel = linkLayer
    .selectAll("line")
    .data(links, (d) => `${d.source}->${d.target}`)
    .join("line")
    .attr("class", "graph-link");

  const nodeSel = nodeLayer
    .selectAll("g.node")
    .data(nodes, (d) => d.id)
    .join((enter) => {
      const g = enter.append("g").attr("class", "node");
      g.append("circle").attr("class", "node-core");
      return g;
    });

  nodeSel
    .select("circle")
    .attr("r", (d) => d.radius)
    .attr("class", (d) =>
      d.kind === "video" ? "node-core node-video stroke-sky-300/40" : "node-core node-person stroke-violet-300/40"
    );

  nodeSel.each(function (d) {
    const g = d3.select(this);
    g.selectAll("clipPath").remove();
    g.selectAll("image.thumb").remove();
    g.selectAll("text.center-glyph").remove();
    if (d.kind === "video") {
      const clipId = `clip-${d.id.replace(/[^a-zA-Z0-9-_]/g, "_")}`;
      g.append("clipPath")
        .attr("id", clipId)
        .append("circle")
        .attr("r", d.radius - 2)
        .attr("cx", 0)
        .attr("cy", 0);
      g.append("image")
        .attr("class", "thumb")
        .attr("href", d.thumbnail)
        .attr("x", -(d.radius - 2))
        .attr("y", -(d.radius - 2))
        .attr("width", (d.radius - 2) * 2)
        .attr("height", (d.radius - 2) * 2)
        .attr("clip-path", `url(#${clipId})`);
    } else {
      const name = d.name || "Unknown";
      const letter = name === "Unknown" ? "?" : name.charAt(0).toUpperCase();
      g.append("text")
        .attr("class", "center-glyph")
        .attr("text-anchor", "middle")
        .attr("dy", "0.35em")
        .text(letter);
    }
  });

  const labelSel = labelLayer
    .selectAll("text.graph-label")
    .data(nodes, (d) => d.id)
    .join("text")
    .attr("class", "graph-label")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => d.radius + 16)
    .text((d) => {
      if (d.kind === "video") {
        const title = d.title || "";
        return title.length > 40 ? `${title.slice(0, 37)}...` : title;
      }
      const name = d.name || "Unknown";
      return name.length > 20 ? `${name.slice(0, 17)}...` : name;
    });

  nodeSel
    .on("click", (_event, d) => {
      updateDetails(d);
      if (d.kind === "video") {
        const cluster = d.cluster;
        nodeSel.classed("dimmed", (node) => node.cluster !== cluster);
        linkSel.classed(
          "dimmed",
          (link) => String(link.target.id ?? link.target).indexOf(`video:${cluster}`) !== 0
        );
      } else {
        nodeSel.classed("dimmed", (node) => node.id !== d.id && node.cluster !== d.cluster);
        linkSel.classed(
          "dimmed",
          (link) =>
            String(link.source.id ?? link.source) !== d.id &&
            String(link.target.id ?? link.target) !== d.id
        );
      }
    })
    .on("mouseenter", (event, d) => {
      const label =
        d.kind === "video"
          ? `${d.title}`
          : `${d.name || "Unknown"} — ${(d.speaker?.word_count || 0).toLocaleString()} words`;
      tooltip.classed("hidden", false).text(label);
      tooltip.style("left", `${event.clientX + 12}px`).style("top", `${event.clientY + 12}px`);
    })
    .on("mousemove", (event) => {
      tooltip.style("left", `${event.clientX + 12}px`).style("top", `${event.clientY + 12}px`);
    })
    .on("mouseleave", () => {
      tooltip.classed("hidden", true);
    });

  nodeSel.call(
    d3
      .drag()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      })
  );

  if (simulation) {
    simulation.stop();
  }
  simulation = d3
    .forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(90).strength(0.6))
    .force("charge", d3.forceManyBody().strength(-220))
    .force("collide", d3.forceCollide().radius((d) => d.radius + 4).iterations(2))
    .force("center", d3.forceCenter(width() / 2, height() / 2))
    .force("x", d3.forceX(width() / 2).strength(0.04))
    .force("y", d3.forceY(height() / 2).strength(0.04))
    .alpha(0.95)
    .on("tick", () => {
      linkSel
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
      labelSel.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });
}

async function loadLibrary() {
  const response = await fetch("/library");
  if (!response.ok) {
    throw new Error("Failed to load library");
  }
  const payload = await response.json();
  const videos = payload.videos || [];
  window.__libraryCache = videos;
  return videos;
}

async function refreshGraph() {
  const videos = await loadLibrary();
  const graphData = buildGraphData(videos);
  renderGraph(graphData);
  setStatus(`Loaded ${videos.length} analyzed video${videos.length === 1 ? "" : "s"}.`);
}

analyzeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    return;
  }
  analyzeButton.disabled = true;
  setStatus("Transcribing... this can take a few minutes.");
  try {
    const response = await fetch("/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        language: "en",
        min_speaker_seconds: 30,
        force_refresh: false,
      }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message = payload.detail || `Request failed (${response.status})`;
      throw new Error(message);
    }
    await refreshGraph();
    showToast("Analysis complete. Graph updated.");
    setStatus("Done.");
    urlInput.value = "";
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    showToast(message, true);
    setStatus(`Error: ${message}`);
  } finally {
    analyzeButton.disabled = false;
  }
});

window.addEventListener("resize", () => {
  graphSvg.attr("viewBox", `0 0 ${width()} ${height()}`);
  if (simulation) {
    simulation.force("center", d3.forceCenter(width() / 2, height() / 2));
    simulation.alpha(0.4).restart();
  }
});

initSvg();
refreshGraph().catch((error) => {
  const message = error instanceof Error ? error.message : "Could not load library.";
  showToast(message, true);
  setStatus(message);
});
