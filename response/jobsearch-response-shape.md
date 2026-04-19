Response
├── data[] // 20 job listings
│ └── {job}
│ ├── id
│ ├── title
│ ├── teaser
│ ├── roleId
│ ├── bulletPoints[]
│ ├── tags[] // optional: URGENT, EXPIRES_SOON, EARLY_APPLICANT
│ │
│ ├── companyName
│ ├── employer
│ │ ├── id
│ │ ├── name
│ │ ├── companyId
│ │ └── companyUrl
│ ├── advertiser
│ │ ├── id
│ │ └── description
│ ├── companyProfileStructuredDataId
│ ├── branding
│ │ └── serpLogoUrl
│ │
│ ├── locations[]
│ │ ├── label
│ │ ├── countryCode
│ │ └── seoHierarchy[]
│ │ └── contextualName
│ │
│ ├── classifications[]
│ │ ├── classification { id, description }
│ │ └── subclassification { id, description }
│ │
│ ├── salaryLabel
│ ├── workTypes[] // Full time | Part time | Contract/Temp
│ ├── workArrangements
│ │ ├── data[] { id, label.text } // On-site | Hybrid | Remote
│ │ └── displayText
│ │
│ ├── listingDate
│ ├── listingDateDisplay // "1h ago"
│ ├── isFeatured
│ ├── displayType // promoted | standard
│ ├── displayStyle.search
│ │
│ ├── externalReferences[] // optional, e.g. recruiter
│ │ ├── id
│ │ ├── sourceSystem
│ │ ├── type
│ │ └── metadata
│ │ ├── name
│ │ └── assets.profilePhotoUrl
│ │
│ ├── tracking // base64 token
│ └── solMetadata
│ ├── searchRequestToken
│ ├── token
│ ├── jobId
│ ├── section
│ ├── sectionRank
│ ├── jobAdType // SPONSORED | ORGANIC
│ └── tags
│
├── totalCount // 7616
├── userQueryId
├── sortModes[] // Relevance (active), Date
│ └── { isActive, name, value }
│
├── info
│ ├── timeTaken
│ ├── source
│ ├── experiment
│ └── newSince
│
├── solMetadata // search-level telemetry
│ ├── requestToken
│ ├── token
│ ├── sortMode
│ ├── categories[]
│ ├── pageSize
│ ├── pageNumber
│ ├── totalJobCount
│ └── tags { ... }
│
├── searchParams
│ ├── classification
│ ├── sitekey
│ └── page
│
└── facets // empty {}
