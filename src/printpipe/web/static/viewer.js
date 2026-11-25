// PrintPipe in-browser 3D model viewer.
// Vanilla ES module, no build step. Three.js + loaders come from the vendored local
// importmap that the host page (run_detail.py) must declare. This file only
// imports the bare specifiers "three" and "three/addons/...".
//
// Usage from the page:
//   <script type="module">
//     import { init } from "/static/viewer.js";
//     init({ canvasId: "model-canvas", url: "/runs/<id>/model.glb", format: "glb" });
//   </script>
// or via the global shim:
//   window.PrintPipeViewer.init({ canvasId, url, format });
//
// format is one of "stl" | "glb" | "gltf" | "3mf". When omitted it is guessed
// from the url extension.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

// 3MFLoader pulls in vendored fflate; load it lazily so loading it never
// breaks the common STL/GLB paths.
let ThreeMFLoaderPromise = null;
function loadThreeMFLoader() {
  if (ThreeMFLoaderPromise === null) {
    ThreeMFLoaderPromise = import("three/addons/loaders/3MFLoader.js").then(
      (mod) => mod.ThreeMFLoader,
    );
  }
  return ThreeMFLoaderPromise;
}

// Bambu P1S / X1 / A1 build plate is 256 x 256 mm.
const BED_SIZE_MM = 256;
const ACCENT = 0x327d9e; // matches RUN_DETAIL_CSS teal accent
const MODEL_COLOR = 0xb8c6d4; // neutral cool grey for STL/3MF without materials

function guessFormat(url) {
  const clean = (url || "").split("?")[0].split("#")[0].toLowerCase();
  const dot = clean.lastIndexOf(".");
  if (dot === -1) {
    return "glb";
  }
  const ext = clean.slice(dot + 1);
  if (ext === "stl" || ext === "glb" || ext === "gltf" || ext === "3mf") {
    return ext;
  }
  return "glb";
}

function showError(host, message) {
  // Render a graceful, theme-matched error inside the figure rather than the
  // browser console only.
  let overlay = host.querySelector(".viewer-error");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "viewer-error";
    host.appendChild(overlay);
  }
  overlay.textContent = message;
  overlay.style.display = "block";
}

function clearError(host) {
  const overlay = host.querySelector(".viewer-error");
  if (overlay) {
    overlay.style.display = "none";
  }
}

function addHint(host) {
  if (host.querySelector(".viewer-hint")) {
    return;
  }
  const hint = document.createElement("div");
  hint.className = "viewer-hint";
  hint.textContent = "drag to orbit · scroll to zoom";
  host.appendChild(hint);
}

// Soft three-point-ish lighting that reads geometry without being harsh.
function addLighting(scene) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa7b4, 0.85));

  const key = new THREE.DirectionalLight(0xffffff, 0.9);
  key.position.set(1, 1.4, 1);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xffffff, 0.35);
  fill.position.set(-1.2, 0.6, -0.8);
  scene.add(fill);

  scene.add(new THREE.AmbientLight(0xffffff, 0.25));
}

// 256 x 256 ground grid representing the print bed, centered on origin.
function addBed(scene) {
  const grid = new THREE.GridHelper(BED_SIZE_MM, 16, ACCENT, 0xcfd8e3);
  grid.material.opacity = 0.55;
  grid.material.transparent = true;
  scene.add(grid);

  // Solid plate so the model has something to sit on visually.
  const plate = new THREE.Mesh(
    new THREE.PlaneGeometry(BED_SIZE_MM, BED_SIZE_MM),
    new THREE.MeshStandardMaterial({
      color: 0xf7fafc,
      roughness: 0.95,
      metalness: 0.0,
      transparent: true,
      opacity: 0.4,
    }),
  );
  plate.rotation.x = -Math.PI / 2;
  plate.position.y = -0.01; // nudge below grid to avoid z-fighting
  scene.add(plate);
}

// Returns the root Object3D for the loaded asset, normalising loader outputs.
function normaliseLoaded(result, format) {
  if (format === "stl") {
    const geometry = result;
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color: MODEL_COLOR,
      roughness: 0.6,
      metalness: 0.05,
      flatShading: false,
    });
    return new THREE.Mesh(geometry, material);
  }
  if (format === "glb" || format === "gltf") {
    return result.scene || result.scenes[0];
  }
  // 3MF and anything Object3D-shaped.
  return result;
}

// Drop the model so it rests on the bed (min Y at 0) and is centered in X/Z,
// then position the camera to frame it with a little margin.
function frameModel(root, camera, controls) {
  const box = new THREE.Box3().setFromObject(root);
  if (box.isEmpty()) {
    return 0;
  }
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  // Recenter X/Z on origin, sit the base on the bed plane (y = 0).
  root.position.x -= center.x;
  root.position.z -= center.z;
  root.position.y -= box.min.y;

  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const fitHeightDistance = maxDim / (2 * Math.tan((Math.PI * camera.fov) / 360));
  const fitWidthDistance = fitHeightDistance / camera.aspect;
  const distance = 1.5 * Math.max(fitHeightDistance, fitWidthDistance);

  const target = new THREE.Vector3(0, size.y / 2, 0);
  camera.position.set(distance * 0.8, distance * 0.7, distance * 0.9);
  camera.near = Math.max(maxDim / 1000, 0.1);
  camera.far = distance * 12;
  camera.updateProjectionMatrix();

  controls.target.copy(target);
  controls.maxDistance = distance * 8;
  controls.minDistance = maxDim * 0.05;
  controls.update();
  return maxDim;
}

export function init(options) {
  const opts = options || {};
  const canvasId = opts.canvasId || "model-canvas";
  const url = opts.url;
  const format = (opts.format || guessFormat(url || "")).toLowerCase();

  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.error(`PrintPipeViewer: canvas #${canvasId} not found`);
    return null;
  }
  const host = canvas.parentElement || canvas;

  if (!url) {
    showError(host, "No model available to preview.");
    return null;
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: false,
    });
  } catch (err) {
    showError(host, "WebGL is not available in this browser.");
    console.error("PrintPipeViewer: WebGL init failed", err);
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  camera.position.set(180, 160, 200);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.85;
  controls.zoomSpeed = 0.9;

  addLighting(scene);
  addBed(scene);
  addHint(host);

  function sizeToHost() {
    const width = Math.max(host.clientWidth || canvas.clientWidth || 1, 1);
    const height = Math.max(host.clientHeight || canvas.clientHeight || 1, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  sizeToHost();

  let disposed = false;
  let modelRoot = null;

  function renderLoop() {
    if (disposed) {
      return;
    }
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(renderLoop);
  }

  function onResize() {
    sizeToHost();
  }
  window.addEventListener("resize", onResize);

  // ResizeObserver catches layout changes that don't fire window resize
  // (e.g. the workbench column reflowing) when available.
  let resizeObserver = null;
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => sizeToHost());
    resizeObserver.observe(host);
  }

  function onLoaded(rawResult) {
    try {
      const root = normaliseLoaded(rawResult, format);
      if (!root) {
        showError(host, "Model loaded but contained no geometry.");
        return;
      }
      modelRoot = root;
      scene.add(root);
      frameModel(root, camera, controls);
      clearError(host);
      // The 3D model is up — hide the legacy 2D SVG/placeholder and the static
      // figcaption overlays (title / dims / risk) so they don't clutter or occlude
      // the canvas; that info is shown in the metrics strip + cards below. The
      // SVG is kept in the DOM as a fallback if WebGL ever fails.
      host.querySelectorAll(".model-preview-image, .mesh-placeholder, figcaption").forEach((el) => {
        el.style.display = "none";
      });
    } catch (err) {
      showError(host, "Could not display the model.");
      console.error("PrintPipeViewer: post-load error", err);
    }
  }

  function onError(err) {
    showError(host, "Failed to load the 3D model.");
    console.error("PrintPipeViewer: load error", err);
  }

  function startLoad(LoaderClass) {
    try {
      const loader = new LoaderClass();
      loader.load(url, onLoaded, undefined, onError);
    } catch (err) {
      onError(err);
    }
  }

  if (format === "stl") {
    startLoad(STLLoader);
  } else if (format === "glb" || format === "gltf") {
    startLoad(GLTFLoader);
  } else if (format === "3mf") {
    loadThreeMFLoader()
      .then((LoaderClass) => startLoad(LoaderClass))
      .catch((err) => {
        showError(host, "3MF preview is unavailable.");
        console.error("PrintPipeViewer: 3MF loader unavailable", err);
      });
  } else {
    showError(host, `Unsupported model format: ${format}`);
    return null;
  }

  renderLoop();

  // Disposer so callers can tear the viewer down if the figure is replaced.
  function dispose() {
    disposed = true;
    window.removeEventListener("resize", onResize);
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    controls.dispose();
    if (modelRoot) {
      modelRoot.traverse((node) => {
        if (node.isMesh) {
          if (node.geometry) {
            node.geometry.dispose();
          }
          const mat = node.material;
          if (Array.isArray(mat)) {
            mat.forEach((m) => m.dispose());
          } else if (mat) {
            mat.dispose();
          }
        }
      });
    }
    renderer.dispose();
  }

  return { scene, camera, renderer, controls, dispose };
}

// Global shim for pages that prefer a non-module call site.
if (typeof window !== "undefined") {
  window.PrintPipeViewer = window.PrintPipeViewer || {};
  window.PrintPipeViewer.init = init;
}

export default { init };
