import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FileText,
  Download,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  AlertCircle,
  Shield,
  Search,
  Layers,
  FileCheck,
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import {
  listFindings,
  getFindingReportPdf,
  InvestigativeFinding,
} from '../api';
import { StatusBadge } from '../components/common/StatusBadge';

// Initialize PDF.js worker using Vite asset URL resolution
if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;
}

export const Reports: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlFindingId = (searchParams.get('id') || '').trim();

  // Findings list state
  const [findings, setFindings] = useState<InvestigativeFinding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<InvestigativeFinding | null>(null);
  const [isLoadingFindings, setIsLoadingFindings] = useState<boolean>(true);
  const [findingsError, setFindingsError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // PDF report generation state
  const [isGeneratingPdf, setIsGeneratingPdf] = useState<boolean>(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(0);
  const [zoomScale, setZoomScale] = useState<number>(1.25);
  const [isRenderingPage, setIsRenderingPage] = useState<boolean>(false);

  // Canvas & cleanup references
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<any>(null);
  const objectUrlRef = useRef<string | null>(null);

  // 1. Fetch real findings from API
  const fetchFindings = async () => {
    try {
      setIsLoadingFindings(true);
      setFindingsError(null);
      const data = await listFindings({ limit: 100 });
      setFindings(data);

      // Select finding from URL param if available, or keep current, or default to first
      if (data.length > 0) {
        if (urlFindingId) {
          const match = data.find((f) => f.finding_id === urlFindingId);
          if (match) {
            setSelectedFinding(match);
          } else {
            setSelectedFinding(data[0]);
          }
        } else if (!selectedFinding) {
          setSelectedFinding(data[0]);
        }
      } else {
        setSelectedFinding(null);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to connect to backend findings repository.';
      setFindingsError(message);
    } finally {
      setIsLoadingFindings(false);
    }
  };

  useEffect(() => {
    fetchFindings();
  }, []);

  // Sync selection with URL query param if changed externally
  useEffect(() => {
    if (urlFindingId && findings.length > 0) {
      const match = findings.find((f) => f.finding_id === urlFindingId);
      if (match && (!selectedFinding || selectedFinding.finding_id !== match.finding_id)) {
        handleSelectFinding(match);
      }
    }
  }, [urlFindingId, findings]);

  // Handle finding selection
  const handleSelectFinding = (finding: InvestigativeFinding) => {
    if (selectedFinding?.finding_id === finding.finding_id) return;
    setSelectedFinding(finding);
    setSearchParams({ id: finding.finding_id });

    // Clean up previous PDF document and object URL
    setPdfDoc(null);
    setPdfError(null);
    setCurrentPage(1);
    setTotalPages(0);
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
      setPdfObjectUrl(null);
    }
  };

  // 2. Generate PDF Report from existing backend endpoint
  const handleGenerateReport = async () => {
    if (!selectedFinding) return;

    try {
      setIsGeneratingPdf(true);
      setPdfError(null);

      const blob = await getFindingReportPdf(selectedFinding.finding_id);

      // Revoke previous object URL safely
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }

      const newUrl = URL.createObjectURL(blob);
      objectUrlRef.current = newUrl;
      setPdfObjectUrl(newUrl);

      // Load document into PDF.js
      const arrayBuffer = await blob.arrayBuffer();
      const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
      const doc = await loadingTask.promise;

      setPdfDoc(doc);
      setTotalPages(doc.numPages);
      setCurrentPage(1);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Backend report generation failed.';
      setPdfError(message);
      setPdfDoc(null);
      setTotalPages(0);
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  // 3. Render current PDF page onto HTML canvas
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let isCancelled = false;

    const renderPage = async () => {
      try {
        setIsRenderingPage(true);
        const page = await pdfDoc.getPage(currentPage);
        if (isCancelled) return;

        const viewport = page.getViewport({ scale: zoomScale });
        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        // Apply device pixel ratio for high DPI / Retina crispness
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        context.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Cancel any pending render task to prevent collision
        if (renderTaskRef.current) {
          renderTaskRef.current.cancel();
        }

        const renderContext = {
          canvasContext: context,
          viewport: viewport,
          canvas: canvas,
        };

        const renderTask = page.render(renderContext);
        renderTaskRef.current = renderTask;

        await renderTask.promise;
      } catch (err: unknown) {
        const errorObj = err as { name?: string };
        if (errorObj?.name !== 'RenderingCancelledException') {
          console.error('PDF.js render error:', err);
        }
      } finally {
        if (!isCancelled) {
          setIsRenderingPage(false);
        }
      }
    };

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [pdfDoc, currentPage, zoomScale]);

  // Clean up object URLs on component unmount
  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
    };
  }, []);

  // Action: Download PDF
  const handleDownload = () => {
    if (!pdfObjectUrl || !selectedFinding) return;
    const safeId = selectedFinding.finding_id.replace(/[^a-zA-Z0-9_-]/g, '_');
    const a = document.createElement('a');
    a.href = pdfObjectUrl;
    a.download = `investigative_report_${safeId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  // Action: Open in new browser tab
  const handleOpenInNewTab = () => {
    if (!pdfObjectUrl) return;
    window.open(pdfObjectUrl, '_blank', 'noopener,noreferrer');
  };

  // Filtered findings list
  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      const matchesSearch =
        searchQuery === '' ||
        f.finding_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (f.pattern_type && f.pattern_type.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus = statusFilter === 'ALL' || f.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [findings, searchQuery, statusFilter]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] p-4 space-y-4 max-w-[1920px] mx-auto text-slate-100">
      {/* Workspace Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-950/60 border border-indigo-800/80 rounded text-indigo-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-indigo-400 tracking-wider">MOD-07-REP</span>
              <span className="text-slate-600">/</span>
              <h1 className="text-lg font-bold text-slate-100 tracking-tight">Investigative Report Workspace</h1>
            </div>
            <p className="text-xs text-slate-400">
              Deterministic, audit-ready analytical reports compiled from typed provenance bundles.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchFindings}
            disabled={isLoadingFindings}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded text-xs font-medium text-slate-300 transition-colors disabled:opacity-50"
            title="Refresh findings from workspace"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoadingFindings ? 'animate-spin' : ''}`} />
            <span>Refresh Findings</span>
          </button>
        </div>
      </div>

      {/* Main Dual-Pane Workspace */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
        {/* Left Pane: Finding Selector Ledger (4 cols) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col bg-slate-900/60 border border-slate-800 rounded-lg overflow-hidden">
          {/* Search & Filter Header */}
          <div className="p-3 border-b border-slate-800 space-y-2 bg-slate-900/90">
            <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
              <span className="flex items-center gap-1.5 uppercase tracking-wider text-[11px] text-slate-300">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Workspace Findings Ledger
              </span>
              <span className="font-mono text-[11px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">
                {filteredFindings.length} / {findings.length}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter by title, ID, or pattern..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-600 transition-colors"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-slate-300 focus:outline-none focus:border-indigo-600"
              >
                <option value="ALL">All Status</option>
                <option value="OPEN">Open</option>
                <option value="IN_REVIEW">In Review</option>
                <option value="RESOLVED">Resolved</option>
                <option value="DISMISSED">Dismissed</option>
              </select>
            </div>
          </div>

          {/* Findings List Scroll Area */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60 p-1">
            {isLoadingFindings ? (
              <div className="p-6 text-center text-xs text-slate-400 space-y-2">
                <RotateCw className="w-5 h-5 animate-spin mx-auto text-indigo-400" />
                <div>Loading findings from workspace...</div>
              </div>
            ) : findingsError ? (
              <div className="p-4 m-2 bg-rose-950/40 border border-rose-800/80 rounded text-xs text-rose-300 space-y-2">
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertCircle className="w-4 h-4 text-rose-400" />
                  <span>Repository Connection Error</span>
                </div>
                <p className="text-[11px] text-rose-300/80">{findingsError}</p>
                <button
                  onClick={fetchFindings}
                  className="px-2.5 py-1 bg-rose-900/60 hover:bg-rose-900 border border-rose-700 rounded text-[11px] font-medium transition-colors"
                >
                  Retry Connection
                </button>
              </div>
            ) : filteredFindings.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 space-y-2">
                <AlertCircle className="w-6 h-6 mx-auto text-slate-600" />
                <div className="font-medium text-slate-300">No Findings Available</div>
                <p className="text-[11px] text-slate-500 max-w-[240px] mx-auto">
                  {findings.length === 0
                    ? 'No investigative findings registered in current workspace. Run analytical pattern detection first.'
                    : 'No findings match current search query or status filter.'}
                </p>
              </div>
            ) : (
              filteredFindings.map((finding) => {
                const isSelected = selectedFinding?.finding_id === finding.finding_id;
                return (
                  <button
                    key={finding.finding_id}
                    onClick={() => handleSelectFinding(finding)}
                    className={`w-full text-left p-3 transition-colors rounded ${
                      isSelected
                        ? 'bg-indigo-950/40 border-l-2 border-indigo-500 text-slate-100'
                        : 'hover:bg-slate-800/40 text-slate-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <span className="font-mono text-[10px] text-slate-400 truncate max-w-[190px]">
                        {finding.finding_id}
                      </span>
                      <StatusBadge status={finding.status} size="sm" />
                    </div>

                    <div className="font-medium text-xs text-slate-200 line-clamp-2 mb-2 leading-snug">
                      {finding.title}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span className="px-1.5 py-0.5 bg-slate-800/80 rounded border border-slate-700/60 text-slate-300 text-[10px]">
                        {finding.pattern_type || 'FINDING'}
                      </span>
                      <span className="flex items-center gap-1 text-slate-500 text-[10px]">
                        <FileCheck className="w-3 h-3 text-slate-400" />
                        {finding.evidence_ids.length} ev
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Pane: Report Inspector & PDF.js Viewer (8 cols) */}
        <div className="col-span-12 lg:col-span-8 flex flex-col space-y-3 min-h-0">
          {selectedFinding ? (
            <>
              {/* Finding Summary & Action Header Card */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="space-y-1 max-w-[70%]">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={selectedFinding.status} size="sm" />
                      <span className="font-mono text-xs text-slate-400">{selectedFinding.finding_id}</span>
                      {selectedFinding.pattern_type && (
                        <span className="font-mono text-[10px] px-1.5 py-0.5 bg-slate-800 rounded text-slate-300 border border-slate-700">
                          {selectedFinding.pattern_type}
                        </span>
                      )}
                    </div>
                    <h2 className="text-sm font-semibold text-slate-100 leading-snug">{selectedFinding.title}</h2>
                  </div>

                  {/* Primary Action Buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleGenerateReport}
                      disabled={isGeneratingPdf}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-950 disabled:text-indigo-400 text-white rounded text-xs font-semibold shadow-sm transition-colors"
                    >
                      <RotateCw className={`w-3.5 h-3.5 ${isGeneratingPdf ? 'animate-spin' : ''}`} />
                      <span>{pdfDoc ? 'Regenerate Report' : 'Generate Analytical PDF Report'}</span>
                    </button>

                    {pdfObjectUrl && (
                      <>
                        <button
                          onClick={handleDownload}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs font-medium text-slate-200 transition-colors"
                          title="Download compiled PDF dossier"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download</span>
                        </button>

                        <button
                          onClick={handleOpenInNewTab}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs font-medium text-slate-300 transition-colors"
                          title="Open PDF in browser tab"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Finding Metadata Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Observed Time Window:</span>
                    <span className="text-slate-300 font-mono">
                      {selectedFinding.time_window?.start_time && selectedFinding.time_window?.end_time
                        ? `${new Date(selectedFinding.time_window.start_time).toLocaleDateString()} — ${new Date(
                            selectedFinding.time_window.end_time
                          ).toLocaleDateString()}`
                        : 'Not temporally bounded'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 block">Supporting Evidence:</span>
                    <span className="text-slate-300 font-mono font-medium">
                      {selectedFinding.evidence_ids.length} records linked
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 block">Referenced Entities:</span>
                    <span className="text-slate-300 font-mono font-medium">
                      {selectedFinding.entity_ids.length} entities involved
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 block">Analytical Signals:</span>
                    <span className="text-slate-300 font-mono font-medium">
                      {selectedFinding.signal_ids.length} signals converged
                    </span>
                  </div>
                </div>
              </div>

              {/* PDF Document Viewer Container */}
              <div className="flex-1 bg-slate-950 border border-slate-800 rounded-lg flex flex-col overflow-hidden relative">
                {/* Viewer Navigation Toolbar */}
                <div className="flex items-center justify-between px-3 py-2 bg-slate-900/90 border-b border-slate-800 text-xs text-slate-300">
                  {/* Page Controls */}
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={!pdfDoc || currentPage <= 1}
                      className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Previous Page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="font-mono text-[11px] px-1.5 py-0.5 bg-slate-950 border border-slate-800 rounded">
                      Page {totalPages > 0 ? currentPage : 0} of {totalPages}
                    </span>
                    <button
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={!pdfDoc || currentPage >= totalPages}
                      className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Next Page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Viewer Banner */}
                  <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-slate-500 font-mono">
                    <Shield className="w-3 h-3 text-slate-400" />
                    <span>CONTROLLED ENVIRONMENT // AUDIT PROVENANCE DOSSIER</span>
                  </div>

                  {/* Zoom Controls */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setZoomScale((s) => Math.max(0.75, s - 0.25))}
                      disabled={!pdfDoc || zoomScale <= 0.75}
                      className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Zoom Out"
                    >
                      <ZoomOut className="w-4 h-4" />
                    </button>
                    <span className="font-mono text-[11px] w-12 text-center text-slate-400">
                      {Math.round(zoomScale * 100)}%
                    </span>
                    <button
                      onClick={() => setZoomScale((s) => Math.min(2.5, s + 0.25))}
                      disabled={!pdfDoc || zoomScale >= 2.5}
                      className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Zoom In"
                    >
                      <ZoomIn className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* PDF Canvas Viewport Area */}
                <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-950/80">
                  {isGeneratingPdf ? (
                    <div className="text-center p-8 space-y-3">
                      <RotateCw className="w-8 h-8 animate-spin mx-auto text-indigo-400" />
                      <div className="text-sm font-semibold text-slate-200">
                        Compiling Provenance &amp; Generating PDF...
                      </div>
                      <p className="text-xs text-slate-400 max-w-sm mx-auto">
                        Calling WeasyPrint report generation engine via backend endpoint. This produces a deterministic,
                        unalterable document.
                      </p>
                    </div>
                  ) : pdfError ? (
                    <div className="max-w-md p-5 bg-rose-950/50 border border-rose-800 rounded-lg text-rose-200 space-y-3 text-center">
                      <AlertCircle className="w-8 h-8 mx-auto text-rose-400" />
                      <div className="text-sm font-semibold">Report Generation Error</div>
                      <p className="text-xs text-rose-300/80 leading-relaxed">{pdfError}</p>
                      <button
                        onClick={handleGenerateReport}
                        className="px-3 py-1.5 bg-rose-900 hover:bg-rose-800 text-white rounded text-xs font-semibold transition-colors"
                      >
                        Retry Report Compilation
                      </button>
                    </div>
                  ) : pdfDoc ? (
                    <div className="relative flex flex-col items-center">
                      {isRenderingPage && (
                        <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[1px] flex items-center justify-center z-10">
                          <RotateCw className="w-6 h-6 animate-spin text-indigo-400" />
                        </div>
                      )}
                      <canvas
                        ref={canvasRef}
                        className="shadow-2xl rounded border border-slate-700/80 bg-white"
                      />
                    </div>
                  ) : (
                    <div className="text-center p-8 space-y-3 max-w-md">
                      <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-400">
                        <FileText className="w-6 h-6" />
                      </div>
                      <div className="text-sm font-semibold text-slate-300">Analytical Report Not Yet Compiled</div>
                      <p className="text-xs text-slate-500 leading-relaxed">
                        Select <span className="text-slate-300 font-medium">"{selectedFinding.title}"</span> and click{' '}
                        <span className="text-indigo-400 font-semibold">Generate Analytical PDF Report</span> to assemble
                        the complete provenance bundle and render an audit-ready dossier using PDF.js.
                      </p>
                      <button
                        onClick={handleGenerateReport}
                        className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold shadow-md transition-colors"
                      >
                        <FileText className="w-4 h-4" />
                        <span>Generate Analytical PDF Report</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 bg-slate-900/40 border border-slate-800 rounded-lg flex items-center justify-center p-8 text-center">
              <div className="space-y-2 max-w-sm">
                <AlertCircle className="w-8 h-8 mx-auto text-slate-600" />
                <div className="text-sm font-semibold text-slate-300">No Finding Selected</div>
                <p className="text-xs text-slate-500">
                  Select an investigative finding from the ledger on the left to inspect its parameters and compile a
                  report.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
