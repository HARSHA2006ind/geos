import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // Initialize Gemini SDK with User-Agent header as required
  const getGeminiClient = () => {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) return null;
    return new GoogleGenAI({
      apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        },
      },
    });
  };

  // API Route: Health check
  app.get('/api/health', (req, res) => {
    res.json({
      status: 'operational',
      engine: 'GeoResilience-NER AI Core',
      geminiConfigured: Boolean(process.env.GEMINI_API_KEY),
      timestamp: new Date().toISOString(),
    });
  });

  // API Route: Explainable AI Geotechnical & Disaster Intelligence Briefing
  app.post('/api/gemini/explain', async (req, res) => {
    try {
      const { location, simulated } = req.body;
      if (!location) {
        return res.status(400).json({ error: 'Location data is required.' });
      }

      const ai = getGeminiClient();
      if (!ai) {
        return res.json({
          source: 'local-deterministic',
          text: null,
          message: 'Gemini API key not configured, using local deterministic XAI engine.',
        });
      }

      const prompt = `You are the chief geotechnical AI advisor for the Disaster Management Authority in the North Eastern Region of India (NER).
Analyze this specific landslide risk location:
- Location: ${location.name} (${location.state}, District: ${location.district})
- Calculated Landslide Risk Score: ${location.calculatedScore}/100 [Classification: ${location.calculatedLevel}]
- 24h Rainfall: ${location.currentRainfall} mm
- Slope Angle: ${location.slope}°
- Elevation: ${location.elevation} meters
- Soil Type: ${location.soilType}
- Soil Saturation Index: ${location.soilSaturation}%
- Historical Landslide Activity Index: ${location.historicalActivity}%
- Exposed Population: ${location.populationExposed} people
- Infrastructure At Risk: ${location.infrastructure.roads} roads (${location.infrastructure.keyHighways?.join(', ')}), ${location.infrastructure.bridges} bridges, ${location.infrastructure.hospitals} hospitals, ${location.infrastructure.schools} schools.
- Simulation Context: ${simulated ? 'This is under an elevated simulated rainfall scenario.' : 'Current baseline monitoring condition.'}

Generate an authoritative, concise 2-paragraph geological and disaster response briefing:
Paragraph 1: Explain the exact physical and hydrometeorological trigger mechanics why this location has this risk score (referencing pore-water pressure, shear stress vs shear strength of the specific soil/rock, antecedent rainfall).
Paragraph 2: Provide specific, pragmatic immediate action directives for District Administration, BRO/NHIDCL highway teams, and local emergency personnel.
Do not invent numerical scores. Keep it professional, urgent, and tailored to the mountainous Himalayan terrain.`;

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: prompt,
      });

      return res.json({
        source: 'gemini-ai',
        text: response.text,
      });
    } catch (err: any) {
      console.error('Error generating AI explanation:', err);
      return res.status(500).json({
        source: 'fallback',
        error: err?.message || 'Failed to generate AI response',
      });
    }
  });

  // API Route: What-If Regional Scenario Briefing
  app.post('/api/gemini/what-if-briefing', async (req, res) => {
    try {
      const { summary, params } = req.body;
      const ai = getGeminiClient();
      if (!ai) {
        return res.json({ source: 'local', text: null });
      }

      const prompt = `You are the Director of the National Disaster Management Authority (NDMA) monitoring the North Eastern Region of India.
A what-if scenario was run with simulated rainfall at ${params?.rainfallMm || 180} mm/24h (Intensity: ${params?.rainfallIntensity || 'Normal'}, Soil Saturation Bonus: ${params?.soilSaturationBonus || 0}%).
Outcome summary:
- Critical Zones changed from ${summary.currentCritical} to ${summary.simulatedCritical} (+${summary.diffCritical})
- High Risk Zones changed from ${summary.currentHigh} to ${summary.simulatedHigh} (+${summary.diffHigh})
- Newly exposed population: +${summary.diffPopulationExposed.toLocaleString()} citizens
- Potentially disrupted road corridors: +${summary.diffRoadsExposed} arterial segments.

Provide a succinct 3-bullet strategic executive briefing for state Chief Secretaries and the Union Home Ministry regarding regional preparedness, pre-positioning NDRF battalions, and supply-chain resilience for isolated hill districts.`;

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: prompt,
      });

      return res.json({
        source: 'gemini-ai',
        text: response.text,
      });
    } catch (err: any) {
      return res.status(500).json({ source: 'fallback', error: err?.message });
    }
  });

  // Vite middleware for development vs static build in production
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`GeoResilience-NER Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Fatal server startup error:', err);
});
