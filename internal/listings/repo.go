package listings

import (
	"context"
	"encoding/json"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Repo encapsulates DB access; swapping implementations later stays easy.
type Repo struct {
	db *pgxpool.Pool
}

func NewRepo(db *pgxpool.Pool) *Repo {
	return &Repo{db: db}
}

// Listing is the shape we expose via the API (mirrors DB columns we care about).
type Listing struct {
	ID           int64        `json:"id"`
	BlockCode    string       `json:"block"`
	City         string       `json:"city"`
	ListingType  string       `json:"listing_type"`
	Title        string       `json:"title"`
	PriceEUR     *int64       `json:"price_eur,omitempty"`
	SizeM2       *float64     `json:"size_m2,omitempty"`
	Rooms        *float64     `json:"rooms,omitempty"`
	Floor        *int16       `json:"floor,omitempty"`
	URL          string       `json:"url"`
	ThumbnailURL *string      `json:"thumbnail_url,omitempty"`
	IsAgency     bool         `json:"is_agency"`
	IsDuplicate  bool         `json:"is_duplicate"`
	PricePerSqm  *float64     `json:"price_per_sqm,omitempty"`
	ListingDate  *string      `json:"listing_date,omitempty"`
	SourceLinks  []SourceLink `json:"source_links,omitempty"`
	DedupeKey    *string      `json:"dedupe_key,omitempty"`
	LastSeenAt   string       `json:"last_seen_at"`
	CreatedAt    string       `json:"created_at"`
}

// SourceLink mirrors the JSONB payload stored in listings.source_links.
type SourceLink struct {
	Source string  `json:"source"`
	URL    string  `json:"url,omitempty"`
	Title  *string `json:"title,omitempty"`
}

// Filters captures query params from the handler.
type Filters struct {
	City           string
	ListingType    string
	Block          string
	MinPrice       *int64
	MaxPrice       *int64
	MinSize        *float64
	MaxSize        *float64
	MinPricePerSqm *float64
	MaxPricePerSqm *float64
	IsAgency       *bool
	Rooms          *float64
	Floor          *int16
	Sort           string
	Limit          int
	Offset         int
}

// List returns active listings using simple SQL construction with placeholders.
func (r *Repo) List(ctx context.Context, f Filters) ([]Listing, error) {
	// Build the WHERE clause progressively while keeping parameters ordered.
	var (
		where []string
		args  []any
	)

	where = append(where, "is_active = true")

	if f.Block != "" {
		args = append(args, f.Block)
		where = append(where, "block_code = $"+itoa(len(args)))
	}
	if f.City != "" {
		args = append(args, f.City)
		where = append(where, "city = $"+itoa(len(args)))
	}
	if f.ListingType != "" {
		args = append(args, f.ListingType)
		where = append(where, "listing_type = $"+itoa(len(args)))
	}
	if f.MinPrice != nil {
		args = append(args, *f.MinPrice)
		where = append(where, "price_eur >= $"+itoa(len(args)))
	}
	if f.MaxPrice != nil {
		args = append(args, *f.MaxPrice)
		where = append(where, "price_eur <= $"+itoa(len(args)))
	}
	if f.MinSize != nil {
		args = append(args, *f.MinSize)
		where = append(where, "size_m2 >= $"+itoa(len(args)))
	}
	if f.MaxSize != nil {
		args = append(args, *f.MaxSize)
		where = append(where, "size_m2 <= $"+itoa(len(args)))
	}
	if f.MinPricePerSqm != nil {
		args = append(args, *f.MinPricePerSqm)
		where = append(where, "price_per_sqm >= $"+itoa(len(args)))
	}
	if f.MaxPricePerSqm != nil {
		args = append(args, *f.MaxPricePerSqm)
		where = append(where, "price_per_sqm <= $"+itoa(len(args)))
	}
	if f.IsAgency != nil {
		args = append(args, *f.IsAgency)
		where = append(where, "is_agency = $"+itoa(len(args)))
	}
	if f.Rooms != nil {
		args = append(args, *f.Rooms)
		where = append(where, "rooms = $"+itoa(len(args)))
	}
	if f.Floor != nil {
		args = append(args, *f.Floor)
		where = append(where, "floor = $"+itoa(len(args)))
	}

	// Default limit to keep responses predictable; cap to prevent abuse.
	limit := f.Limit
	if limit <= 0 || limit > 500 {
		limit = 500
	}
	args = append(args, limit)

	// Optional offset for pagination.
	offsetClause := ""
	if f.Offset > 0 {
		args = append(args, f.Offset)
		offsetClause = " OFFSET $" + itoa(len(args))
	}

	orderBy := `
		ORDER BY
			COALESCE(listing_date::timestamptz, created_at) DESC,
			last_seen_at DESC,
			id DESC`

	switch strings.ToLower(f.Sort) {
	case "price_asc":
		orderBy = `
		ORDER BY
			price_eur IS NULL,
			price_eur ASC,
			id DESC`
	case "price_desc":
		orderBy = `
		ORDER BY
			price_eur IS NULL,
			price_eur DESC,
			id DESC`
	case "price_per_sqm_asc":
		orderBy = `
		ORDER BY
			price_per_sqm IS NULL,
			price_per_sqm ASC,
			id DESC`
	case "price_per_sqm_desc":
		orderBy = `
		ORDER BY
			price_per_sqm IS NULL,
			price_per_sqm DESC,
			id DESC`
	case "listing_date_asc":
		orderBy = `
		ORDER BY
			COALESCE(listing_date::timestamptz, created_at) ASC,
			last_seen_at ASC,
			id DESC`
	case "listing_date_desc":
		// same as default; keep descending recency
	}

	sql := `
		SELECT
			id,
			block_code,
			city,
			listing_type,
			title,
			price_eur,
			size_m2,
			rooms,
			floor,
			url,
			thumbnail_url,
			is_agency,
			is_duplicate,
			price_per_sqm,
			listing_date::text AS listing_date,
			source_links,
			dedupe_key,
			last_seen_at::text AS last_seen_at,
			created_at::text AS created_at
		FROM listings
		WHERE ` + strings.Join(where, " AND ") + `
		` + orderBy + `
		LIMIT $` + itoa(len(args)) + offsetClause

	rows, err := r.db.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Listing
	for rows.Next() {
		var l Listing
		var sourceLinksRaw []byte
		if err := rows.Scan(
			&l.ID,
			&l.BlockCode,
			&l.City,
			&l.ListingType,
			&l.Title,
			&l.PriceEUR,
			&l.SizeM2,
			&l.Rooms,
			&l.Floor,
			&l.URL,
			&l.ThumbnailURL,
			&l.IsAgency,
			&l.IsDuplicate,
			&l.PricePerSqm,
			&l.ListingDate,
			&sourceLinksRaw,
			&l.DedupeKey,
			&l.LastSeenAt,
			&l.CreatedAt,
		); err != nil {
			return nil, err
		}
		if len(sourceLinksRaw) > 0 {
			_ = json.Unmarshal(sourceLinksRaw, &l.SourceLinks)
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

// itoa is a tiny helper to avoid importing strconv everywhere.
func itoa(i int) string {
	return strconv.Itoa(i)
}

// Optionally: add upsert/insert methods here when wiring scrapers to the DB.
