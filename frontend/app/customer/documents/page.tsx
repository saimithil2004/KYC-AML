"use client";

import React, { useEffect, useState } from "react";
import { Upload } from "lucide-react";
import { ProtectedRoute } from "../../../components/ProtectedRoute";
import { buttonClass, FormField, inputClass } from "../../../components/FormField";
import { useAuth } from "../../../context/AuthContext";
import { API_BASE_URL, DocumentRecord, ensureCustomer } from "../../../lib/api";

export default function DocumentUploadPage() {
  const { token } = useAuth();
  const [customerId, setCustomerId] = useState("");
  const [documentType, setDocumentType] = useState("passport");
  const [file, setFile] = useState<File | null>(null);
  const [lastUpload, setLastUpload] = useState<DocumentRecord | null>(null);
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    if (!token) return;
    ensureCustomer(token).then((customer) => setCustomerId(customer.id)).catch(console.error);
  }, [token]);

  const uploadDocument = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token || !customerId || !file) return;
    setStatusMsg("Uploading document...");

    const formData = new FormData();
    formData.append("customer_id", customerId);
    formData.append("document_type", documentType);
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Upload failed");
      }
      const document = (await response.json()) as DocumentRecord;
      setLastUpload(document);
      setStatusMsg("Document uploaded and queued for verification.");
    } catch (error) {
      setStatusMsg(error instanceof Error ? error.message : "Document upload failed.");
    }
  };

  return (
    <ProtectedRoute>
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-zinc-950">Document Upload</h1>
          <p className="text-zinc-600">Upload PDF, PNG, JPG, or JPEG verification documents.</p>
        </div>
        <form onSubmit={uploadDocument} className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="space-y-4">
            <FormField label="Document Type">
              <select className={inputClass} value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
                <option value="passport">Passport</option>
                <option value="driving_license">Driving License</option>
                <option value="utility_bill">Utility Bill</option>
                <option value="bank_statement">Bank Statement</option>
              </select>
            </FormField>
            <FormField label="File">
              <input required type="file" accept=".pdf,.png,.jpg,.jpeg" className={inputClass} onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </FormField>
          </div>
          <button className={`${buttonClass} mt-5 gap-2`} type="submit">
            <Upload className="h-4 w-4" />
            Upload Document
          </button>
          {statusMsg && <p className="mt-4 text-sm text-teal-700">{statusMsg}</p>}
          {lastUpload && <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700">Uploaded: {lastUpload.file_name} ({lastUpload.verification_status})</div>}
        </form>
      </div>
    </ProtectedRoute>
  );
}
