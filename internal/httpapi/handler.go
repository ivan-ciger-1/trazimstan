package httpapi

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"appartment/internal/listings"
)

// Handler bundles the service so we can add methods cleanly.
type Handler struct {
	svc *listings.Service
}

// NewHandler constructs a Handler; keeps wiring in one place.
func NewHandler(svc *listings.Service) *Handler {
	return &Handler{svc: svc}
}

// ListBlocks returns the known blocks. For now this is static; later it can be DB-backed.
func (h *Handler) ListBlocks(w http.ResponseWriter, r *http.Request) {
	blocks := h.svc.ListBlocks(r.Context())
	respondJSON(w, http.StatusOK, blocks)
}

// ListListings returns listings filtered by block and price/size ranges.
func (h *Handler) ListListings(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()

	f := listings.Filters{
		Block:          q.Get("block"),
		Limit:          parseInt(q.Get("limit")),
		Offset:         parseInt(q.Get("offset")),
		Sort:           q.Get("sort"),
		MinPricePerSqm: parseFloat64Ptr(q.Get("min_price_per_sqm")),
		MaxPricePerSqm: parseFloat64Ptr(q.Get("max_price_per_sqm")),
		Rooms:          parseFloat64Ptr(q.Get("rooms")),
		Floor:          parseInt16Ptr(q.Get("floor")),
		IsAgency:       parseBoolPtr(q.Get("is_agency")),
	}
	if v := parseInt64Ptr(q.Get("min_price")); v != nil {
		f.MinPrice = v
	}
	if v := parseInt64Ptr(q.Get("max_price")); v != nil {
		f.MaxPrice = v
	}
	if v := parseFloat64Ptr(q.Get("min_size")); v != nil {
		f.MinSize = v
	}
	if v := parseFloat64Ptr(q.Get("max_size")); v != nil {
		f.MaxSize = v
	}

	items, err := h.svc.List(r.Context(), f)
	if err != nil {
		// Log the underlying error so 500s are debuggable.
		log.Printf("list listings: %v", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	respondJSON(w, http.StatusOK, items)
}

// parseInt is forgiving: invalid values fall back to zero rather than 400s.
func parseInt(s string) int {
	if s == "" {
		return 0
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return 0
	}
	return v
}

func parseInt64Ptr(s string) *int64 {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return nil
	}
	return &v
}

func parseFloat64Ptr(s string) *float64 {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return nil
	}
	return &v
}

func parseInt16Ptr(s string) *int16 {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseInt(s, 10, 16)
	if err != nil {
		return nil
	}
	val := int16(v)
	return &val
}

func parseBoolPtr(s string) *bool {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseBool(s)
	if err != nil {
		return nil
	}
	return &v
}

func respondJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v) // ignore encoding error for simplicity
}
