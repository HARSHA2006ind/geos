import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import {
  Layers,
  ZoomIn,
  ZoomOut,
  Compass,
  MapPin,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  RiskLocation,
  HistoricalLandslide,
  FieldReport,
  MapLayerSettings,
} from '../../types/disaster';

interface RiskMapProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  historicalLandslides: HistoricalLandslide[];
  fieldReports: FieldReport[];
  isSimulated?: boolean;
}

export const RiskMap: React.FC<RiskMapProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  historicalLandslides,
  fieldReports,
  isSimulated = false,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerGroupsRef = useRef<{ [key: string]: L.LayerGroup }>({});

  const [mapType, setMapType] = useState<'satellite' | 'dark'>('satellite');
  const [isLayersCollapsed, setIsLayersCollapsed] = useState(false);

  const [layers, setLayers] = useState<MapLayerSettings>({
    riskZones: true,
    historicalLandslides: true,
    rainfall: true,
    roads: true,
    settlements: true,
    hospitals: true,
    schools: false,
    infrastructure: true,
    fieldReports: true,
  });

  const toggleLayer = (layerKey: keyof MapLayerSettings) => {
    setLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  // Highway corridors mock coordinates in NER
  const highwayLines = [
    {
      name: 'NH-13 (Trans-Arunachal Highway)',
      color: '#38bdf8',
      coords: [
        [27.586, 91.865], // Tawang
        [27.264, 92.423], // Bomdila
        [27.084, 93.605], // Itanagar
        [27.95, 94.85],   // Pasighat
      ] as [number, number][],
    },
    {
      name: 'NH-10 (Sikkim Lifeline)',
      color: '#f43f5e',
      coords: [
        [26.85, 88.42],  // Siliguri
        [27.167, 88.36], // Namchi
        [27.338, 88.60], // Gangtok
        [27.512, 88.52], // Mangan
      ] as [number, number][],
    },
    {
      name: 'NH-29 (Dimapur-Kohima Corridor)',
      color: '#fbbf24',
      coords: [
        [25.91, 93.72],  // Dimapur
        [25.675, 94.108], // Kohima
        [25.267, 94.018], // Senapati
        [24.832, 94.021], // Imphal
      ] as [number, number][],
    },
    {
      name: 'NH-6 (Guwahati-Shillong-Silchar)',
      color: '#34d399',
      coords: [
        [26.144, 91.736], // Guwahati
        [25.903, 91.879], // Nongpoh
        [25.578, 91.893], // Shillong
        [25.178, 93.024], // Haflong
      ] as [number, number][],
    },
  ];

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Centered over North Eastern Region of India
    const map = L.map(mapContainerRef.current, {
      center: [26.05, 92.8],
      zoom: 7,
      minZoom: 6,
      maxZoom: 14,
      zoomControl: false,
      attributionControl: false,
    });

    mapRef.current = map;

    // Base tile layers
    const satelliteTiles = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 }
    );

    const darkTiles = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { maxZoom: 18 }
    );

    // Default to satellite as shown in the screenshot
    if (mapType === 'satellite') {
      satelliteTiles.addTo(map);
    } else {
      darkTiles.addTo(map);
    }

    (map as any)._satelliteTiles = satelliteTiles;
    (map as any)._darkTiles = darkTiles;

    // Initialize layer groups
    const groups = {
      riskZones: L.layerGroup().addTo(map),
      historicalLandslides: L.layerGroup().addTo(map),
      rainfall: L.layerGroup().addTo(map),
      roads: L.layerGroup().addTo(map),
      settlements: L.layerGroup().addTo(map),
      hospitals: L.layerGroup().addTo(map),
      schools: L.layerGroup().addTo(map),
      infrastructure: L.layerGroup().addTo(map),
      fieldReports: L.layerGroup().addTo(map),
    };

    layerGroupsRef.current = groups;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Switch Tile Base
  useEffect(() => {
    const map = mapRef.current as any;
    if (!map) return;

    if (mapType === 'satellite') {
      if (map._darkTiles && map.hasLayer(map._darkTiles)) {
        map.removeLayer(map._darkTiles);
      }
      if (map._satelliteTiles && !map.hasLayer(map._satelliteTiles)) {
        map.addLayer(map._satelliteTiles);
      }
    } else {
      if (map._satelliteTiles && map.hasLayer(map._satelliteTiles)) {
        map.removeLayer(map._satelliteTiles);
      }
      if (map._darkTiles && !map.hasLayer(map._darkTiles)) {
        map.addLayer(map._darkTiles);
      }
    }
  }, [mapType]);

  // Redraw Layers
  useEffect(() => {
    const map = mapRef.current;
    const groups = layerGroupsRef.current;
    if (!map || !groups.riskZones) return;

    // Clear previous
    Object.values(groups as Record<string, L.LayerGroup>).forEach((g) => g.clearLayers());

    // 1. Roads & Arteries
    if (layers.roads) {
      highwayLines.forEach((hwy) => {
        const polyline = L.polyline(hwy.coords, {
          color: hwy.color,
          weight: 3,
          opacity: 0.85,
          dashArray: '4, 6',
        });
        polyline.bindTooltip(
          `<div class="font-bold text-xs">${hwy.name}</div><div class="text-[10px] text-slate-300">Strategic Himalayan Highway Corridor</div>`,
          { className: 'bg-slate-900 text-white rounded p-1 border border-slate-700' }
        );
        polyline.addTo(groups.roads);
      });
    }

    // 2. Risk Zones (Dominant interactive circles & pulse halos)
    if (layers.riskZones) {
      locations.forEach((loc) => {
        const isSelected = selectedLocation?.id === loc.id;
        const color =
          loc.calculatedLevel === 'CRITICAL'
            ? '#ef4444'
            : loc.calculatedLevel === 'HIGH'
            ? '#f97316'
            : loc.calculatedLevel === 'MODERATE'
            ? '#eab308'
            : '#22c55e';

        // Size adapts to score & simulation status
        const baseRadius = isSimulated ? loc.calculatedScore * 450 : loc.calculatedScore * 350;

        // Outer glow halo circle
        const halo = L.circle([loc.lat, loc.lng], {
          radius: Math.max(12000, baseRadius),
          color: color,
          fillColor: color,
          fillOpacity: isSelected ? 0.45 : isSimulated ? 0.35 : 0.22,
          weight: isSelected ? 3 : 1.5,
        });

        // Interactive core marker
        const coreMarker = L.circleMarker([loc.lat, loc.lng], {
          radius: isSelected ? 11 : 8,
          color: '#ffffff',
          fillColor: color,
          fillOpacity: 0.95,
          weight: 2,
        });

        const popupContent = `
          <div style="font-family: sans-serif;">
            <div style="font-weight: 700; font-size: 13px; color: #fff; margin-bottom: 2px;">${loc.name}</div>
            <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">${loc.district}, ${loc.state}</div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
              <span style="background: ${color}22; color: ${color}; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 11px; border: 1px solid ${color}66;">
                ${loc.calculatedLevel} RISK (${loc.calculatedScore}/100)
              </span>
              <span style="font-size: 10px; color: #94a3b8;">Conf: ${loc.confidence}%</span>
            </div>
            <div style="font-size: 10px; color: #cbd5e1; line-height: 1.3;">
              • Rain: <b>${loc.currentRainfall} mm</b> | Slope: <b>${loc.slope}°</b><br/>
              • Pop Exposed: <b>${loc.populationExposed.toLocaleString()}</b>
            </div>
          </div>
        `;

        coreMarker.bindTooltip(popupContent, {
          sticky: true,
          className: 'bg-slate-900/95 text-white border border-slate-700 rounded-lg shadow-xl',
        });

        coreMarker.on('click', () => {
          onSelectLocation(loc);
        });
        halo.on('click', () => {
          onSelectLocation(loc);
        });

        halo.addTo(groups.riskZones);
        coreMarker.addTo(groups.riskZones);
      });
    }

    // 3. Historical Landslide markers
    if (layers.historicalLandslides) {
      historicalLandslides.forEach((hist) => {
        const histIcon = L.divIcon({
          className: 'custom-hist-icon',
          html: `<div style="background: #dc2626; color: white; width: 18px; height: 18px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; border: 1px solid white; box-shadow: 0 0 8px rgba(220,38,38,0.7);">▲</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });

        const marker = L.marker([hist.lat, hist.lng], { icon: histIcon });
        marker.bindTooltip(
          `<div class="font-bold text-xs text-red-400">HISTORICAL LANDSLIDE (${hist.year})</div>
           <div class="font-semibold text-white text-xs">${hist.locationName}</div>
           <div class="text-[10px] text-slate-300">Fatalities: ${hist.fatalities} | Rain: ${hist.rainfallRecorded} mm</div>
           <div class="text-[9px] text-slate-400 mt-1">${hist.damageDescription}</div>`,
          { className: 'bg-slate-900 border border-red-500/40 rounded p-1.5 max-w-xs' }
        );
        marker.addTo(groups.historicalLandslides);
      });
    }

    // 4. Rainfall Indicators
    if (layers.rainfall) {
      locations.forEach((loc) => {
        if (loc.currentRainfall > 100) {
          const rainIcon = L.divIcon({
            className: 'custom-rain-icon',
            html: `<div style="background: rgba(14, 116, 144, 0.85); border: 1px solid #38bdf8; color: #e0f2fe; padding: 1px 4px; border-radius: 8px; font-size: 9px; font-weight: bold; font-family: monospace; white-space: nowrap; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">
              💧 ${loc.currentRainfall}mm
            </div>`,
            iconAnchor: [20, 20],
          });
          L.marker([loc.lat + 0.08, loc.lng - 0.08], { icon: rainIcon }).addTo(groups.rainfall);
        }
      });
    }

    // 5. Settlements
    if (layers.settlements) {
      locations.forEach((loc) => {
        const dot = L.circleMarker([loc.lat - 0.04, loc.lng + 0.04], {
          radius: 4,
          fillColor: '#60a5fa',
          fillOpacity: 0.8,
          color: '#ffffff',
          weight: 1,
        });
        dot.bindTooltip(
          `<div class="text-xs font-semibold">${loc.name} Habitation</div><div class="text-[10px] text-slate-300">Pop: ${loc.populationExposed.toLocaleString()}</div>`,
          { className: 'bg-slate-900 text-white rounded p-1 border border-slate-700' }
        );
        dot.addTo(groups.settlements);
      });
    }

    // 6. Hospitals
    if (layers.hospitals) {
      locations.forEach((loc) => {
        if (loc.infrastructure.hospitals > 0) {
          const hospIcon = L.divIcon({
            className: 'custom-hosp-icon',
            html: `<div style="background: #a855f7; color: white; width: 14px; height: 14px; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 900; border: 1px solid white;">✚</div>`,
            iconSize: [14, 14],
            iconAnchor: [7, -10],
          });
          L.marker([loc.lat, loc.lng], { icon: hospIcon })
            .bindTooltip(
              `<div class="text-xs font-bold text-purple-300">Healthcare Facilities: ${loc.infrastructure.hospitals}</div><div class="text-[10px] text-slate-300">Emergency trauma unit active at ${loc.district}</div>`,
              { className: 'bg-slate-900 text-white border border-purple-500/40 rounded p-1' }
            )
            .addTo(groups.hospitals);
        }
      });
    }

    // 7. Critical Infrastructure (Bridges, Power)
    if (layers.infrastructure) {
      locations.forEach((loc) => {
        if (loc.infrastructure.bridges > 0) {
          const bridgeIcon = L.divIcon({
            className: 'custom-bridge-icon',
            html: `<div style="background: #06b6d4; color: #082f49; width: 14px; height: 14px; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: bold; border: 1px solid white;">🌉</div>`,
            iconSize: [14, 14],
            iconAnchor: [-10, 7],
          });
          L.marker([loc.lat, loc.lng], { icon: bridgeIcon })
            .bindTooltip(
              `<div class="text-xs font-bold text-cyan-400">Bridges: ${loc.infrastructure.bridges} | Power Assets: ${loc.infrastructure.powerAssets}</div>`,
              { className: 'bg-slate-900 text-white border border-cyan-500/40 rounded p-1' }
            )
            .addTo(groups.infrastructure);
        }
      });
    }

    // 8. Field Reports
    if (layers.fieldReports) {
      fieldReports.forEach((rep) => {
        const color =
          rep.severity === 'Critical'
            ? '#ef4444'
            : rep.severity === 'High'
            ? '#f97316'
            : rep.severity === 'Moderate'
            ? '#eab308'
            : '#22c55e';

        const repIcon = L.divIcon({
          className: 'custom-rep-icon',
          html: `<div style="background: ${color}; color: white; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; border: 2px solid white; box-shadow: 0 0 10px ${color};">!</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        });

        L.marker([rep.lat, rep.lng], { icon: repIcon })
          .bindTooltip(
            `<div class="text-xs font-bold" style="color: ${color}">FIELD OBSERVATION: ${rep.type.toUpperCase()}</div>
             <div class="font-medium text-white text-xs">${rep.locationName}</div>
             <div class="text-[10px] text-slate-300">By ${rep.submittedBy} (${rep.role}) • ${rep.timestamp}</div>
             <div class="text-[9px] text-slate-400 mt-1">${rep.description}</div>`,
            { className: 'bg-slate-900 border border-slate-700 rounded p-1.5 max-w-xs' }
          )
          .addTo(groups.fieldReports);
      });
    }
  }, [locations, selectedLocation, historicalLandslides, fieldReports, layers, isSimulated]);

  // Center on Selected Location when changed externally
  useEffect(() => {
    if (!selectedLocation || !mapRef.current) return;
    mapRef.current.flyTo([selectedLocation.lat, selectedLocation.lng], 9, {
      duration: 1.2,
      easeLinearity: 0.25,
    });
  }, [selectedLocation]);

  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();
  const handleRecenter = () => {
    mapRef.current?.flyTo([26.05, 92.8], 7, { duration: 1.0 });
  };

  return (
    <div className="relative w-full h-full min-h-[420px] rounded-xl overflow-hidden border border-slate-800 bg-[#080c14] shadow-2xl">
      {/* Map Canvas */}
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Floating Layer Control Panel (Top-Left, exactly matching mockup) */}
      <div className="absolute top-3 left-3 z-10 w-52 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg shadow-2xl overflow-hidden transition-all duration-200">
        <div
          onClick={() => setIsLayersCollapsed(!isLayersCollapsed)}
          className="px-3 py-2 bg-slate-800/80 flex items-center justify-between cursor-pointer border-b border-slate-700/60"
        >
          <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span>Map Layers</span>
          </div>
          <button
            id="map-toggle-layer-panel-btn"
            className="text-slate-400 hover:text-white"
          >
            {isLayersCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>

        {!isLayersCollapsed && (
          <div className="p-2 space-y-1.5 text-xs">
            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.riskZones}
                onChange={() => toggleLayer('riskZones')}
                className="rounded border-slate-700 text-red-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
              <span className="text-slate-200 text-[11px] font-medium">Risk Zones</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.historicalLandslides}
                onChange={() => toggleLayer('historicalLandslides')}
                className="rounded border-slate-700 text-amber-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-red-400 text-[10px] font-bold">▲</span>
              <span className="text-slate-200 text-[11px] font-medium">Historical Landslides</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.rainfall}
                onChange={() => toggleLayer('rainfall')}
                className="rounded border-slate-700 text-cyan-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-cyan-400 text-[10px]">💧</span>
              <span className="text-slate-200 text-[11px] font-medium">Rainfall (24h)</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.roads}
                onChange={() => toggleLayer('roads')}
                className="rounded border-slate-700 text-blue-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-sky-400 text-[10px]">🛣️</span>
              <span className="text-slate-200 text-[11px] font-medium">Roads</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.settlements}
                onChange={() => toggleLayer('settlements')}
                className="rounded border-slate-700 text-indigo-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-indigo-400 text-[10px]">👥</span>
              <span className="text-slate-200 text-[11px] font-medium">Settlements</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.hospitals}
                onChange={() => toggleLayer('hospitals')}
                className="rounded border-slate-700 text-purple-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-purple-400 text-[10px]">✚</span>
              <span className="text-slate-200 text-[11px] font-medium">Hospitals</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.infrastructure}
                onChange={() => toggleLayer('infrastructure')}
                className="rounded border-slate-700 text-teal-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-teal-400 text-[10px]">🌉</span>
              <span className="text-slate-200 text-[11px] font-medium">Critical Infrastructure</span>
            </label>

            <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={layers.fieldReports}
                onChange={() => toggleLayer('fieldReports')}
                className="rounded border-slate-700 text-rose-500 focus:ring-0 w-3.5 h-3.5 bg-slate-950"
              />
              <span className="text-rose-400 text-[10px]">🚩</span>
              <span className="text-slate-200 text-[11px] font-medium">Field Reports</span>
            </label>
          </div>
        )}
      </div>

      {/* Floating Risk Legend (Bottom-Left) */}
      <div className="absolute bottom-3 left-3 z-10 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg p-2.5 shadow-2xl text-[11px] space-y-1 font-mono">
        <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Risk Level</div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 ring-2 ring-red-500/20"></span>
          <span className="text-slate-200">Critical (75-100)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
          <span className="text-slate-200">High (50-74)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500"></span>
          <span className="text-slate-200">Moderate (25-49)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
          <span className="text-slate-200">Low (0-24)</span>
        </div>
      </div>

      {/* Map Tools Controls (Top-Right) */}
      <div className="absolute top-3 right-3 z-10 flex flex-col gap-1.5">
        <button
          id="map-zoom-in-btn"
          onClick={handleZoomIn}
          className="w-8 h-8 rounded-lg bg-slate-900/90 backdrop-blur border border-slate-700 text-slate-200 hover:bg-slate-800 flex items-center justify-center shadow-lg transition"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          id="map-zoom-out-btn"
          onClick={handleZoomOut}
          className="w-8 h-8 rounded-lg bg-slate-900/90 backdrop-blur border border-slate-700 text-slate-200 hover:bg-slate-800 flex items-center justify-center shadow-lg transition"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          id="map-style-toggle-btn"
          onClick={() => setMapType(mapType === 'satellite' ? 'dark' : 'satellite')}
          className="w-8 h-8 rounded-lg bg-slate-900/90 backdrop-blur border border-slate-700 text-slate-200 hover:bg-slate-800 flex items-center justify-center shadow-lg transition"
          title={`Toggle Map Style (Current: ${mapType})`}
        >
          <Layers className="w-4 h-4 text-cyan-400" />
        </button>
        <button
          id="map-recenter-btn"
          onClick={handleRecenter}
          className="w-8 h-8 rounded-lg bg-slate-900/90 backdrop-blur border border-slate-700 text-slate-200 hover:bg-slate-800 flex items-center justify-center shadow-lg transition"
          title="Recenter NER Region"
        >
          <Compass className="w-4 h-4 text-emerald-400" />
        </button>
      </div>

      {/* Scale Bar Marker (Bottom-Right) */}
      <div className="absolute bottom-3 right-3 z-10 bg-slate-900/80 backdrop-blur border border-slate-700/60 rounded px-2 py-0.5 text-[10px] font-mono text-slate-300">
        <div className="w-16 h-1 bg-slate-400 mb-0.5"></div>
        <span>100 km</span>
      </div>
    </div>
  );
};
