"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { getAIModels, createAIModel, createModelVersion, deleteAIModel } from "@/lib/api";
import type { AIModel } from "@/lib/types";
import {
  Cpu, Plus, CheckCircle2, AlertTriangle, Trash2, Layers, Server,
  RefreshCw, Play, X
} from "lucide-react";

export default function ModelRegistryPage() {
  const { token } = useAuth();
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Modal controls
  const [showModelModal, setShowModelModal] = useState(false);
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState("");

  // Form states
  const [modelName, setModelName] = useState("");
  const [modelProvider, setModelProvider] = useState("gemini");
  const [versionName, setVersionName] = useState("");
  const [metadataStr, setMetadataStr] = useState('{"temperature": 0.0, "max_tokens": 1024}');

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const res = await getAIModels(token);
      setModels(res);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to load model registry.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !modelName) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await createAIModel(token, { name: modelName, provider: modelProvider, is_active: true });
      setSuccessMsg(`Model '${modelName}' registered successfully.`);
      setModelName("");
      setShowModelModal(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create model.");
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedModelId || !versionName) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      let metadata = {};
      try {
        metadata = JSON.parse(metadataStr);
      } catch {
        throw new Error("Invalid JSON configuration format.");
      }
      await createModelVersion(token, selectedModelId, { version: versionName, metadata_json: metadata });
      setSuccessMsg(`Model version '${versionName}' added successfully.`);
      setVersionName("");
      setShowVersionModal(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to register model version.");
    }
  };

  const handleDeleteModel = async (id: string) => {
    if (!token || !confirm("Are you sure you want to delete this model from the registry?")) return;
    try {
      setErrorMsg("");
      setSuccessMsg("");
      await deleteAIModel(token, id);
      setSuccessMsg("Model deleted successfully.");
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to delete model.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Loading model registry...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
            <Cpu className="h-6 w-6 text-teal-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Model Registry</h1>
            <p className="text-xs text-zinc-400">Manage LLM configurations, version switches, and custom hyperparameter options</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowModelModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 hover:bg-teal-500 text-xs font-semibold rounded-lg text-white transition-colors"
          >
            <Plus className="h-4 w-4" /> Register Model
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm">
          <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
          <p className="font-semibold">{successMsg}</p>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
          <p className="font-semibold">{errorMsg}</p>
        </div>
      )}

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {models.map((model) => (
          <div key={model.id} className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4 shadow-xs relative">
            <div className="flex justify-between items-start">
              <div>
                <span className={`px-2 py-0.5 text-[9px] font-bold border rounded-full ${
                  model.is_active ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-zinc-100 text-zinc-800 border-zinc-200"
                }`}>
                  {model.is_active ? "ACTIVE" : "INACTIVE"}
                </span>
                <h3 className="text-base font-bold text-zinc-800 mt-2 font-mono">{model.name}</h3>
                <p className="text-[10px] text-zinc-400 font-semibold uppercase mt-0.5">Provider: {model.provider}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setSelectedModelId(model.id);
                    setShowVersionModal(true);
                  }}
                  className="px-2 py-1.5 border hover:bg-zinc-50 text-[10px] font-bold text-zinc-600 rounded-md transition-colors flex items-center gap-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Version
                </button>
                <button
                  onClick={() => handleDeleteModel(model.id)}
                  className="p-1.5 border hover:bg-rose-50 text-rose-600 rounded-md transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Versions Table */}
            <div className="space-y-2 border-t pt-3">
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
                <Layers className="h-3.5 w-3.5 text-zinc-400" /> Version History
              </p>
              <div className="space-y-1.5">
                {model.versions.map((ver) => (
                  <div key={ver.id} className="flex justify-between items-center text-xs p-2.5 bg-zinc-50 border rounded-lg">
                    <span className="font-mono font-bold text-zinc-700">{ver.version}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-zinc-400 font-mono">{JSON.stringify(ver.metadata)}</span>
                      <span className={`h-2 w-2 rounded-full ${ver.is_active ? "bg-emerald-500" : "bg-zinc-300"}`}></span>
                    </div>
                  </div>
                ))}
                {model.versions.length === 0 && (
                  <p className="text-[10px] text-zinc-400 text-center py-2 font-medium">No versions registered under this model.</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Register Model Modal */}
      {showModelModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <Server className="h-4.5 w-4.5 text-teal-600" /> Register AI Provider Model
              </h3>
              <button onClick={() => setShowModelModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <form onSubmit={handleCreateModel} className="space-y-4 text-xs font-semibold text-zinc-700">
              <div className="space-y-1.5">
                <label>Model Identifier (e.g. gemini-2.0-flash)</label>
                <input
                  type="text"
                  required
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Provider Type</label>
                <select
                  value={modelProvider}
                  onChange={(e) => setModelProvider(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 focus:outline-teal-600"
                >
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                  <option value="claude">Claude</option>
                  <option value="local">Local LLM</option>
                </select>
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-zinc-900 text-white font-bold rounded-lg text-xs hover:bg-zinc-850 transition-colors"
              >
                Register Model Instance
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Register Version Modal */}
      {showVersionModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-zinc-200 max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                <Layers className="h-4.5 w-4.5 text-teal-600" /> Create Model Version Snapshot
              </h3>
              <button onClick={() => setShowVersionModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4.5 w-4.5" />
              </button>
            </div>
            <form onSubmit={handleCreateVersion} className="space-y-4 text-xs font-semibold text-zinc-700">
              <div className="space-y-1.5">
                <label>Version Tag (e.g. v1.0, latest)</label>
                <input
                  type="text"
                  required
                  value={versionName}
                  onChange={(e) => setVersionName(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <div className="space-y-1.5">
                <label>Hyperparameters Config (JSON)</label>
                <textarea
                  rows={4}
                  value={metadataStr}
                  onChange={(e) => setMetadataStr(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-zinc-800 font-mono focus:outline-teal-600"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-zinc-900 text-white font-bold rounded-lg text-xs hover:bg-zinc-850 transition-colors"
              >
                Submit Version Snapshot
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
