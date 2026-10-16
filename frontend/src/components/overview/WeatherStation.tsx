import {
  Component,
  memo,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html, Line } from "@react-three/drei";
import * as THREE from "three";
import {
  Anemometer,
  BaseBoard,
  Controller,
  LCD,
  RainGauge,
  SoilMoisture,
  SolarPanel,
  Structure,
  PrintedLabel,
  WindVane,
} from "./StationParts";
import { sensors, type SensorId, type Telemetry } from "./stationData";

interface Props {
  selected: SensorId | null;
  onSelect: (id: SensorId | null) => void;
  autoRotate: boolean;
  motion: boolean;
  exploded: boolean;
  labels: boolean;
  view: string;
  reset: number;
  zoom: number;
  data: Telemetry | null;
  sensorMotion: boolean;
}
class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="scene-message">
        <strong>3D view unavailable</strong>
        <p>
          Your browser could not render this scene. You can still explore every
          component in the list.
        </p>
        <button onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function Rig({
  selected,
  view,
  reset,
  zoom,
  autoRotate,
  motion,
  exploded,
}: Props) {
  const controls = useRef<any>(null);
  const { camera, size, invalidate } = useThree();
  const goal = useRef(new THREE.Vector3());
  const target = useRef(new THREE.Vector3(0.6, 1.5, 0.6));
  const moving = useRef(true);
  const pauseUntil = useRef(0);
  useEffect(() => {
    const aspect = size.width / Math.max(size.height, 1);
    const distance =
      Math.max(10, 13.5 / Math.max(aspect, 0.35)) *
      (exploded ? 1.2 : 1) *
      Math.pow(0.83, zoom);
    const sensor = sensors.find((s) => s.id === selected);
    const center = sensor
      ? new THREE.Vector3(...(exploded ? sensor.exploded : sensor.position))
      : new THREE.Vector3(0.6, 1.5, 0.6);
    target.current.copy(center);
    const offset =
      view === "top"
        ? new THREE.Vector3(0, distance, distance * 0.04)
        : view === "front"
          ? new THREE.Vector3(0, distance * 0.18, distance)
          : new THREE.Vector3(distance * 0.5, distance * 0.42, distance);
    if (sensor) offset.multiplyScalar(0.57);
    if (offset.length()<4.2) offset.setLength(4.2);
    goal.current.copy(center).add(offset);
    moving.current = true;
    invalidate();
  }, [
    selected,
    view,
    reset,
    zoom,
    size.width,
    size.height,
    exploded,
    invalidate,
  ]);
  useFrame((_, delta) => {
    if (!controls.current) return;
    controls.current.autoRotate =
      autoRotate &&
      motion &&
      !selected &&
      !moving.current &&
      performance.now() > pauseUntil.current;
    if (!moving.current) return;
    camera.position.lerp(goal.current, motion ? 1 - Math.exp(-delta * 4) : 1);
    controls.current.target.lerp(
      target.current,
      motion ? 1 - Math.exp(-delta * 4) : 1,
    );
    controls.current.update();
    if (
      camera.position.distanceTo(goal.current) < 0.015 &&
      controls.current.target.distanceTo(target.current) < 0.015
    )
      moving.current = false;
    else invalidate();
  });
  return (
    <OrbitControls
      ref={controls}
      enablePan={false}
      minDistance={4}
      maxDistance={
        Math.max(10, 13.5 / Math.max(size.width / size.height, 0.35)) *
        (exploded ? 1.2 : 1) *
        Math.sqrt(view === "top" ? 1.0016 : view === "front" ? 1.0324 : 1.4264) * 1.002
      }
      minPolarAngle={0.02}
      maxPolarAngle={Math.PI / 2.02}
      autoRotate={autoRotate && motion && !selected && !moving.current}
      autoRotateSpeed={0.35}
      onStart={() => {
        moving.current = false;
        pauseUntil.current = performance.now() + 4000;
      }}
    />
  );
}
function Assembly(props: Props) {
  const directionNames = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
  ];
  const directionIndex = directionNames.indexOf(
    (props.data?.windDirection || "N").toUpperCase(),
  );
  const direction = (Math.max(0, directionIndex) * Math.PI) / 8;
  const models = {
    windVane: WindVane,
    anemometer: Anemometer,
    rainGauge: RainGauge,
    controller: Controller,
    lcd: LCD,
    solarPanel: SolarPanel,
    soilSensor: SoilMoisture,
  };
  return (
    <group>
      <BaseBoard
        isActive={props.selected === "board"}
        onClick={() =>
          props.onSelect(props.selected === "board" ? null : "board")
        }
      />
      <Structure />
      {sensors.map((sensor, index) => {
        const Model = models[sensor.id];
        const position = props.exploded ? sensor.exploded : sensor.position;
        const active = props.selected === sensor.id;
        return (
          <group key={sensor.id}>
            <Model
              position={[...position]}
              isActive={active}
              onClick={() => props.onSelect(active ? null : sensor.id)}
              isRotating={props.motion && props.sensorMotion}
              speed={props.data?.windSpeed ?? 0}
              direction={direction}
              reading={
                props.data?.temperature == null
                  ? "NO SIGNAL"
                  : `${props.data.temperature.toFixed(1)} C`
              }
            />
            {active && (
              <mesh
                position={[position[0], position[1] - 0.12, position[2]]}
                rotation={[-Math.PI / 2, 0, 0]}
              >
                <ringGeometry args={[0.7, 0.76, 48]} />
                <meshBasicMaterial color="#c6f087" side={THREE.DoubleSide} />
              </mesh>
            )}
            {props.exploded && (
              <Line
                points={[[...sensor.position], [...sensor.exploded]]}
                color="#6b9f8d"
                lineWidth={1}
                dashed
                dashSize={0.12}
                gapSize={0.12}
              />
            )}
            {props.labels && (
              <Html
                position={
                  props.exploded
                    ? [position[0], position[1] + 1.4, position[2]]
                    : [...sensor.label]
                }
                center
                occlude
                zIndexRange={[20, 0]}
              >
                <button
                  className={`model-label ${active ? "is-active" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    props.onSelect(active ? null : sensor.id);
                  }}
                  aria-label={sensor.name}
                  title={sensor.name}
                  aria-pressed={active}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <span className="label-name">{sensor.name}</span>
                </button>
              </Html>
            )}
          </group>
        );
      })}
      {/* Fasteners, circuit traces and insulated sensor leads. */}
      {[-3.3, 3.3].flatMap((x) =>
        [-1.5, 2.5].map((z) => (
          <group key={`${x}-${z}`} position={[x, 0.17, z]}>
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.08, 0.08, 0.04, 12]} />
              <meshStandardMaterial
                color="#c6d4d0"
                metalness={0.85}
                roughness={0.3}
              />
            </mesh>
            <mesh position={[0, 0.03, 0]}>
              <boxGeometry args={[0.09, 0.01, 0.018]} />
              <meshStandardMaterial color="#293a35" />
            </mesh>
          </group>
        )),
      )}
      {!props.exploded && (
        <>
          {[
            [
              [-2.5, 2.7, 0],
              [-0.15, 2.7, 0],
              [-0.15, 0.25, 0],
              [0.6, 0.25, -0.2],
            ],
            [
              [2.5, 2.7, 0],
              [0.15, 2.7, 0],
              [0.15, 0.27, 0],
              [0.6, 0.27, -0.2],
            ],
            [
              [3.8, 0.25, 1.5],
              [3, 0.25, 0.7],
              [0.8, 0.25, -0.2],
            ],
            [
              [1.8, 0.25, 1.2],
              [1.2, 0.25, 0.8],
              [0.8, 0.25, -0.2],
            ],
          ].map((points, i) => (
            <Line
              key={i}
              points={points as [number, number, number][]}
              color={i % 2 ? "#b89055" : "#22322d"}
              lineWidth={2}
            />
          ))}
        </>
      )}
      <PrintedLabel
        text="AGRISENSE / WS01"
        position={[-2.3, 0.17, 2.4]}
        rotation={[-Math.PI / 2, 0, 0]}
        width={1.6}
        height={0.22}
        color="#7f9272"
      />
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.17, 0]}
        receiveShadow
      >
        <planeGeometry args={[200, 200]} />
        <shadowMaterial transparent opacity={0.18} />
      </mesh>
    </group>
  );
}
export function WeatherStation(props: Props) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return (
    <SceneBoundary>
      <Suspense
        fallback={
          <div className="scene-message">
            <span className="loading-dot" />
            <p>Preparing your station…</p>
          </div>
        }
      >
        <Canvas
          shadows
          dpr={[1, 1.5]}
          frameloop={
            visible && props.motion && (props.autoRotate || props.sensorMotion)
              ? "always"
              : "demand"
          }
          camera={{ position: [9, 8, 19], fov: 38, near: 0.1, far: 250 }}
          gl={{ antialias: true, powerPreference: "low-power" }}
          onPointerMissed={() => props.onSelect(null)}
        >
          <ambientLight intensity={1.2} />
          <hemisphereLight args={["#edf7f1", "#71867a", 1.5]} />
          <directionalLight
            position={[5, 12, 8]}
            intensity={2.5}
            castShadow
            shadow-mapSize={[1024, 1024]}
            shadow-camera-left={-12}
            shadow-camera-right={12}
            shadow-camera-top={12}
            shadow-camera-bottom={-12}
            shadow-bias={-0.001}
          />
          <directionalLight
            position={[-8, 5, -4]}
            intensity={1.2}
            color="#bfddd0"
          />
          <Rig {...props} />
          <Assembly {...props} />
        </Canvas>
      </Suspense>
    </SceneBoundary>
  );
}

export default memo(WeatherStation);
