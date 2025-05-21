from typing import List, Dict, Any, Optional
from pymongo import UpdateOne, DESCENDING
import logging # Added logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import re # Import re for regular expressions
import json # Import json for parsing and serializing

from app.models.article import Article
from app.db import get_article_collection # This will now be an async function
from app.services.llm_service import LLMService
from config.settings import settings # Added settings import

logger = logging.getLogger(__name__)

# Initialize LLMService globally or pass as a dependency
llm_service = LLMService()

# Prompt template for triage analysis
TRIAGE_PROMPT_TEMPLATE = """
You are an expert media analyst evaluating news coverage. Analyze this article content to identify reporting patterns and information framing:

ARTICLE CONTENT:
{content}

Provide a comprehensive analysis with these components:

1. Category: Classify the article (Science, Technology, Politics, Environment, Health, Business, Sports, Entertainment, Education, Other).

2. Sentiment: Identify the nuanced tone using ONLY one of these categories:
   - Optimistic (positive outlook on future)
   - Encouraging (positive developments)
   - Celebratory (commemorating achievements)
   - Critical (points out flaws or concerns)
   - Cautionary (warns about potential risks)
   - Alarming (raises serious concerns about dangers)
   - Factual (primarily fact-based without obvious bias)
   - Analytical (in-depth analysis with balanced perspective)
   - Balanced (deliberately presents multiple viewpoints)
   - Controversial (contains polarizing content)
   - Sensationalist (exaggerated/dramatic presentation)
   - Mixed (contains multiple sentiment elements)

3. Key Claim: Summarize the main assertion or finding concisely (max 100 words).

4. Requires Deeper Analysis: Flag "Yes" if the topic is complex, controversial, or has significant societal impact; otherwise "No".

5. Keywords: Provide 3-5 specific, descriptive keywords that uniquely identify this article's main topic.

6. Main Entities: Identify key people, organizations, locations, and events in the article. For each entity, specify:
   - The entity name
   - Entity type (PERSON, ORGANIZATION, LOCATION, EVENT, OTHER)
   - Role in article (Subject, Source, Authority, Critic, Beneficiary, Victim, Other)

7. Narrative Focus: Analyze how the story is being told:
   - Primary Focus (choose ONE): Facts/Events, People/Characters, Conflict, Impact/Outcomes, Context/Background, Opinions/Reactions, Process/Mechanics, or Controversy/Debate
   - Emphasized Aspects: List 1-3 specific elements receiving extra emphasis

8. Source Style: Characterize the reporting approach:
   - Depth: In-depth, Standard, or Brief/Superficial
   - Formality: Formal, Semi-formal, or Conversational
   - Technical Level: Expert, Specialist, or General audience
   - Use of Sources: Multiple cited sources, Limited sources, or No clear sourcing

Return your response as a properly formatted JSON object with the following keys: "category", "sentiment", "key_claim", "requires_deep_analysis", "keywords", "main_entities", "narrative_focus", "source_style".

Example (partial):
{
  "category": "Science",
  "sentiment": "Cautionary", 
  "key_claim": "A new study shows plastic-eating bacteria could help with ocean pollution, but scientists warn it's not a complete solution.",
  "requires_deep_analysis": "Yes",
  "keywords": ["marine bacteria", "plastic pollution", "ocean remediation", "biodegradation"],
  "main_entities": [
    {"text": "Nature Journal", "type": "ORGANIZATION", "role": "Source"},
    {"text": "Deep-sea bacteria", "type": "OTHER", "role": "Subject"}
  ],
  "narrative_focus": {
    "primary_focus": "Impact/Outcomes",
    "emphasized_aspects": ["environmental benefits", "scientific limitations"]
  },
  "source_style": {
    "depth": "In-depth",
    "formality": "Semi-formal",
    "technical_level": "General audience",
    "use_of_sources": "Multiple cited sources" 
  }
}
"""

# Prompt template for deep analysis
DEEP_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert media analyst conducting a detailed examination of news coverage. Your task is to deeply analyze this article with particular attention to how the source frames information, what aspects it emphasizes or omits, and what this reveals about the source's reporting approach.

ARTICLE CONTENT:
{content}

Analyze the article in detail, covering these essential areas:

1. POLITICAL AND BIAS ASSESSMENT
   * political_leaning_detected: Categorize as "Left-leaning", "Right-leaning", "Centrist", "Neutral/Objective", or "Unclear"
   * bias_indicators: Identify types of bias present, with specific examples:
     - "Loaded language" - Emotionally charged wording
     - "Selective reporting" - Emphasizing certain facts while downplaying others
     - "Ad hominem attacks" - Attacking character rather than substance
     - "Appeal to emotion" - Using emotional triggers rather than logical arguments
     - "Unsubstantiated claims" - Claims without supporting evidence
     - "Framing bias" - How the issue is characterized or presented
     - "False equivalence" - Treating unequal positions as equal
     - "None detected" - No clear bias observed

2. KEY ARGUMENTS AND CONTENT
   * main_arguments: Summarize 2-4 key arguments or points presented (each as a separate string)

3. INFORMATION QUALITY ASSESSMENT
   * information_quality: Evaluate factual presentation:
     - verifiable_claims_count: Number of distinct, verifiable factual claims
     - cites_sources_within_text: Whether article mentions sources, studies, reports, or named informants
     - evidence_types: Types of evidence used (expert opinions, research studies, data/statistics, historical examples, personal anecdotes, official documents, unnamed sources, or none)
     - context_completeness: How well the article provides necessary context ("Complete", "Partial", "Minimal", or "Misleading")

4. SOURCE APPROACH ANALYSIS
   * source_analysis: Characterize the journalism approach:
     - reporting_style: Overall approach (straight news, analysis/interpretation, opinion/commentary, investigative, explainer/educational, advocacy)
     - perspective_diversity: Range of viewpoints (multiple balanced, multiple with bias, limited, or single perspective)
     - audience_targeting: Intended audience (broad public, politically aligned audience, special interest group, expert audience)

5. FRAMING ANALYSIS
   * framing_devices: How the subject is presented:
     - primary_frame: Main framework (economic, political, moral/ethical, scientific/technical, human interest, conflict/controversy, historic/precedent, security/threat, justice/rights, progress/innovation)
     - metaphors_used: Key metaphors or analogies used
     - emphasis_techniques: Methods used to highlight certain aspects (repetition, vivid descriptions, emotional language, authoritative quotes, statistics, historical parallels, dire predictions, positive forecasting)

6. COMPARATIVE ANALYSIS
   * comparative_indicators: What distinguishes this coverage:
     - unique_perspectives: Viewpoints that might be missing in other coverage
     - potential_omissions: Important aspects seemingly omitted or downplayed
     - emphasis_pattern: What this source emphasizes (factual details, political implications, economic impacts, moral concerns, historical context, future implications, personal stories, conflict, expert views)

7. OVERALL ASSESSMENT
   * analysis_confidence: Your confidence in this analysis ("High", "Medium", "Low")

Return your analysis as a well-structured JSON object with the exact keys specified above.

Example (partial):
{{
  "political_leaning_detected": "Left-leaning",
  "bias_indicators": [
    {{"type": "Framing bias", "example": "Describes corporate tax policies as 'fairness measures' rather than neutral terminology"}},
    {{"type": "Selective reporting", "example": "Mentions benefits to social programs but omits potential economic drawbacks"}}
  ],
  "main_arguments": [
    "The new policy will reduce wealth inequality by redistributing resources from corporations to social programs",
    "Critics from the business sector claim the policy would reduce economic competitiveness",
    "Supporters argue similar policies have succeeded in Nordic countries"
  ],
  "information_quality": {{
    "verifiable_claims_count": 7,
    "cites_sources_within_text": true,
    "evidence_types": ["Expert opinions", "Data/statistics", "Historical examples"],
    "context_completeness": "Partial"
  }}
}}
"""

# JSON schema for triage analysis
TRIAGE_JSON_SCHEMA = {
    "type": "object",
    "required": ["category", "sentiment", "key_claim", "requires_deep_analysis", "keywords", "main_entities", "narrative_focus", "source_style"],
    "properties": {
        "category": {
            "type": "string",
            "description": "The main category of the article",
            "enum": ["Science", "Technology", "Politics", "Environment", "Health", "Business", "Sports", "Entertainment", "Education", "Other"]
        },
        "sentiment": {
            "type": "string",
            "description": "The nuanced sentiment or tone of the article",
            "enum": [
                "Optimistic",       # Positive outlook on future developments
                "Encouraging",      # Presents positive developments
                "Celebratory",      # Commemorating achievements or milestones
                "Critical",         # Points out flaws or concerns
                "Cautionary",       # Warning about potential risks
                "Alarming",         # Raising serious concerns about danger or threats
                "Factual",          # Primarily fact-based reporting without obvious bias
                "Analytical",       # In-depth analysis with balanced perspective
                "Balanced",         # Deliberately presents multiple viewpoints
                "Controversial",    # Contains polarizing content or perspectives
                "Sensationalist",   # Exaggerated or dramatic presentation
                "Mixed"             # Contains multiple sentiment elements
            ]
        },
        "key_claim": {
            "type": "string",
            "description": "A concise summary of the main assertion or finding (max 100 words)"
        },
        "requires_deep_analysis": {
            "type": "string",
            "description": "Flag if the topic is complex, controversial, or has significant societal impact",
            "enum": ["Yes", "No"]
        },
        "keywords": {
            "type": "array",
            "description": "3-5 specific, descriptive keywords that uniquely identify this article's main topic",
            "items": {
                "type": "string"
            },
            "minItems": 3,
            "maxItems": 5
        },
        "main_entities": {
            "type": "array",
            "description": "List of the most important named entities in the article: people, organizations, locations, events",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The name of the entity"
                    },
                    "type": {
                        "type": "string",
                        "description": "The type of entity",
                        "enum": ["PERSON", "ORGANIZATION", "LOCATION", "EVENT", "OTHER"]
                    },
                    "role": {
                        "type": "string", 
                        "description": "The role this entity plays in the article",
                        "enum": ["Subject", "Source", "Authority", "Critic", "Beneficiary", "Victim", "Other"]
                    }
                },
                "required": ["text", "type"]
            }
        },
        "narrative_focus": {
            "type": "object",
            "description": "The aspect of the story that receives the most attention",
            "properties": {
                "primary_focus": {
                    "type": "string",
                    "description": "The primary focus of the article",
                    "enum": [
                        "Facts/Events",       # Focus on describing what happened
                        "People/Characters",  # Focus on individuals involved
                        "Conflict",           # Focus on disagreement or struggle
                        "Impact/Outcomes",    # Focus on consequences and results
                        "Context/Background", # Focus on historical or situational framing
                        "Opinions/Reactions", # Focus on what people think about the events
                        "Process/Mechanics",  # Focus on how something works/happened
                        "Controversy/Debate"  # Focus on divisive aspects
                    ]
                },
                "emphasized_aspects": {
                    "type": "array",
                    "description": "Specific elements of the story that receive extra emphasis",
                    "items": {
                        "type": "string"
                    },
                    "maxItems": 3
                }
            },
            "required": ["primary_focus", "emphasized_aspects"]
        },
        "source_style": {
            "type": "object",
            "description": "Characteristics of the source's reporting approach in this article",
            "properties": {
                "depth": {
                    "type": "string",
                    "enum": ["In-depth", "Standard", "Brief/Superficial"]
                },
                "formality": {
                    "type": "string",
                    "enum": ["Formal", "Semi-formal", "Conversational"]
                },
                "technical_level": {
                    "type": "string",
                    "enum": ["Expert", "Specialist", "General audience"]
                },
                "use_of_sources": {
                    "type": "string",
                    "enum": ["Multiple cited sources", "Limited sources", "No clear sourcing"]
                }
            },
            "required": ["depth", "formality", "technical_level", "use_of_sources"]
        }
    }
}

# JSON schema for deep analysis
DEEP_ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "required": [
        "political_leaning_detected", 
        "bias_indicators", 
        "main_arguments", 
        "information_quality",
        "source_analysis", 
        "framing_devices",
        "comparative_indicators", 
        "analysis_confidence"
    ],
    "properties": {
        "political_leaning_detected": {
            "type": "string",
            "description": "The political leaning detected in the article",
            "enum": ["Left-leaning", "Right-leaning", "Centrist", "Neutral/Objective", "Unclear"]
        },
        "bias_indicators": {
            "type": "array",
            "description": "List of bias types detected in the article",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "Loaded language",
                            "Selective reporting",
                            "Ad hominem attacks",
                            "Appeal to emotion",
                            "Unsubstantiated claims",
                            "Framing bias",
                            "False equivalence",
                            "None detected"
                        ]
                    },
                    "example": {
                        "type": "string",
                        "description": "A specific example from the text"
                    }
                },
                "required": ["type"]
            }
        },
        "main_arguments": {
            "type": "array",
            "description": "Summarize 2-4 key arguments or points presented in the article",
            "items": {
                "type": "string"
            },
            "minItems": 2,
            "maxItems": 4
        },
        "information_quality": {
            "type": "object",
            "description": "Assessment of factual information quality",
            "properties": {
                "verifiable_claims_count": {
                    "type": "integer",
                    "description": "Estimate of the number of distinct, objectively verifiable claims made in the text"
                },
                "cites_sources_within_text": {
                    "type": "boolean",
                    "description": "Whether the article text mentions specific sources, studies, reports, or named individuals providing information"
                },
                "evidence_types": {
                    "type": "array",
                    "description": "Types of evidence used to support claims",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Expert opinions",
                            "Research/studies",
                            "Data/statistics",
                            "Historical examples",
                            "Personal anecdotes",
                            "Official documents",
                            "Unnamed sources",
                            "None provided"
                        ]
                    }
                },
                "context_completeness": {
                    "type": "string",
                    "description": "How well the article provides necessary context for understanding the topic",
                    "enum": ["Complete", "Partial", "Minimal", "Misleading"]
                }
            },
            "required": ["verifiable_claims_count", "cites_sources_within_text", "evidence_types", "context_completeness"]
        },
        "source_analysis": {
            "type": "object",
            "description": "Analysis of the source's approach to reporting",
            "properties": {
                "reporting_style": {
                    "type": "string",
                    "description": "The overall approach to reporting",
                    "enum": [
                        "Straight news reporting",
                        "Analysis/interpretation",
                        "Opinion/commentary",
                        "Investigative reporting",
                        "Explainer/educational",
                        "Advocacy journalism"
                    ]
                },
                "perspective_diversity": {
                    "type": "string",
                    "description": "How many different perspectives are represented",
                    "enum": [
                        "Multiple balanced perspectives",
                        "Multiple perspectives with clear bias",
                        "Limited perspectives",
                        "Single perspective only"
                    ]
                },
                "audience_targeting": {
                    "type": "string",
                    "description": "Who the article appears to be targeting",
                    "enum": [
                        "Broad general public",
                        "Politically aligned audience",
                        "Special interest group",
                        "Expert/technical audience"
                    ]
                }
            },
            "required": ["reporting_style", "perspective_diversity", "audience_targeting"]
        },
        "framing_devices": {
            "type": "object",
            "description": "How the article frames the subject matter",
            "properties": {
                "primary_frame": {
                    "type": "string",
                    "description": "The dominant framing device used",
                    "enum": [
                        "Economic",
                        "Political",
                        "Moral/ethical",
                        "Scientific/technical",
                        "Human interest",
                        "Conflict/controversy",
                        "Historic/precedent",
                        "Security/threat",
                        "Justice/rights",
                        "Progress/innovation"
                    ]
                },
                "metaphors_used": {
                    "type": "array",
                    "description": "Key metaphors or analogies used to frame the issue",
                    "items": {
                        "type": "string"
                    }
                },
                "emphasis_techniques": {
                    "type": "array",
                    "description": "Techniques used to emphasize certain aspects of the story",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Repetition",
                            "Vivid descriptions",
                            "Emotional language",
                            "Authoritative quotations",
                            "Statistical emphasis",
                            "Historical parallels",
                            "Dire predictions",
                            "Positive forecasting"
                        ]
                    }
                }
            },
            "required": ["primary_frame", "emphasis_techniques"]
        },
        "comparative_indicators": {
            "type": "object",
            "description": "Elements that would distinguish this coverage from others on the same topic",
            "properties": {
                "unique_perspectives": {
                    "type": "array",
                    "description": "Perspectives included that might be missing in other coverage",
                    "items": {
                        "type": "string"
                    },
                    "maxItems": 3
                },
                "potential_omissions": {
                    "type": "array",
                    "description": "Important aspects of the story that appear to be omitted or downplayed",
                    "items": {
                        "type": "string"
                    },
                    "maxItems": 3
                },
                "emphasis_pattern": {
                    "type": "string",
                    "description": "What this source seems to emphasize compared to typical coverage",
                    "enum": [
                        "Factual details",
                        "Political implications",
                        "Economic impacts",
                        "Moral/ethical concerns",
                        "Historical context",
                        "Future implications",
                        "Personal stories",
                        "Conflict aspects",
                        "Expert perspectives"
                    ]
                }
            },
            "required": ["unique_perspectives", "potential_omissions", "emphasis_pattern"]
        },
        "analysis_confidence": {
            "type": "string",
            "description": "Confidence level in this analysis",
            "enum": ["High", "Medium", "Low"]
        }
    }
}

# JSON schema for comparative analysis between related articles from different sources
COMPARATIVE_ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "required": ["story_core_facts", "source_differences", "information_gaps", "framing_comparison", "language_analysis", "source_interests", "analysis_limitations"],
    "properties": {
        "story_core_facts": {
            "type": "object",
            "description": "Core facts agreed upon across all sources",
            "properties": {
                "core_event": {
                    "type": "string",
                    "description": "The basic event or situation being reported"
                },
                "core_entities": {
                    "type": "array",
                    "description": "Key entities that appear in all or most sources",
                    "items": {
                        "type": "string"
                    }
                },
                "consistent_details": {
                    "type": "array",
                    "description": "Facts or details consistently reported across sources",
                    "items": {
                        "type": "string"
                    },
                    "minItems": 1
                }
            },
            "required": ["core_event", "core_entities", "consistent_details"]
        },
        "source_differences": {
            "type": "array",
            "description": "Analysis of how each source differs in their coverage",
            "items": {
                "type": "object",
                "properties": {
                    "source_name": {
                        "type": "string",
                        "description": "The name of the source"
                    },
                    "distinctive_focus": {
                        "type": "string",
                        "description": "What this source uniquely emphasizes"
                    },
                    "distinctive_angle": {
                        "type": "string",
                        "description": "The unique perspective or angle this source takes"
                    },
                    "unique_entities": {
                        "type": "array",
                        "description": "Entities mentioned only in this source",
                        "items": {
                            "type": "string"
                        }
                    },
                    "apparent_priorities": {
                        "type": "array",
                        "description": "What seems most important to this source based on emphasis",
                        "items": {
                            "type": "string"
                        },
                        "maxItems": 3
                    }
                },
                "required": ["source_name", "distinctive_focus", "distinctive_angle", "apparent_priorities"]
            },
            "minItems": 2
        },
        "information_gaps": {
            "type": "array",
            "description": "Important information included in some sources but missing in others",
            "items": {
                "type": "object",
                "properties": {
                    "information_item": {
                        "type": "string",
                        "description": "The specific information that varies across sources"
                    },
                    "present_in": {
                        "type": "array",
                        "description": "Sources that include this information",
                        "items": {
                            "type": "string"
                        }
                    },
                    "absent_in": {
                        "type": "array",
                        "description": "Sources that omit this information",
                        "items": {
                            "type": "string"
                        }
                    },
                    "significance": {
                        "type": "string",
                        "description": "Why this information gap is significant",
                        "enum": ["Critical context", "Alternative perspective", "Contradictory evidence", "Qualifying information", "Background detail"]
                    }
                },
                "required": ["information_item", "present_in", "absent_in", "significance"]
            }
        },
        "framing_comparison": {
            "type": "object",
            "description": "How different sources frame the same core story",
            "properties": {
                "framing_dimensions": {
                    "type": "array",
                    "description": "Key dimensions where framing differs between sources",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {
                                "type": "string",
                                "enum": [
                                    "Responsibility/blame attribution",
                                    "Problem definition",
                                    "Moral evaluation",
                                    "Solution proposal",
                                    "Conflict emphasis",
                                    "Economic impact",
                                    "Human impact",
                                    "Political implications",
                                    "Historical context"
                                ]
                            },
                            "variations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "frame_variant": {
                                            "type": "string",
                                            "description": "A specific way the dimension is framed"
                                        },
                                        "sources": {
                                            "type": "array",
                                            "description": "Sources using this frame",
                                            "items": {
                                                "type": "string"
                                            }
                                        }
                                    },
                                    "required": ["frame_variant", "sources"]
                                }
                            }
                        },
                        "required": ["dimension", "variations"]
                    }
                },
                "dominant_narrative": {
                    "type": "string",
                    "description": "The most common narrative across sources"
                },
                "counter_narratives": {
                    "type": "array",
                    "description": "Alternative narratives presented by certain sources",
                    "items": {
                        "type": "object",
                        "properties": {
                            "narrative": {
                                "type": "string"
                            },
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["narrative", "sources"]
                    }
                }
            },
            "required": ["framing_dimensions", "dominant_narrative"]
        },
        "language_analysis": {
            "type": "object",
            "description": "Analysis of language differences between sources",
            "properties": {
                "tone_variations": {
                    "type": "array",
                    "description": "How tone varies between sources",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tone_type": {
                                "type": "string",
                                "enum": [
                                    "Alarmist",
                                    "Reassuring",
                                    "Clinical/detached",
                                    "Empathetic",
                                    "Authoritative",
                                    "Questioning",
                                    "Doubtful",
                                    "Celebratory",
                                    "Condemning"
                                ]
                            },
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["tone_type", "sources"]
                    }
                },
                "charged_language": {
                    "type": "array",
                    "description": "Notable emotionally charged terminology by source",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string"
                            },
                            "examples": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "maxItems": 3
                            }
                        },
                        "required": ["source", "examples"]
                    }
                }
            },
            "required": ["tone_variations"]
        },
        "source_interests": {
            "type": "array",
            "description": "Analysis of what each source seems most interested in based on their coverage",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string"
                    },
                    "apparent_interests": {
                        "type": "array",
                        "description": "Topics or angles this source seems particularly interested in",
                        "items": {
                            "type": "string"
                        },
                        "maxItems": 3
                    },
                    "possible_motivations": {
                        "type": "array",
                        "description": "Potential motivations for this source's coverage approach",
                        "items": {
                            "type": "string",
                            "enum": [
                                "Audience appeal",
                                "Political alignment",
                                "Business/economic interests",
                                "Expertise/specialization",
                                "Ideological commitment",
                                "Regional focus",
                                "Sensationalism/engagement",
                                "Educational mission"
                            ]
                        },
                        "maxItems": 2
                    }
                },
                "required": ["source", "apparent_interests", "possible_motivations"]
            }
        },
        "analysis_limitations": {
            "type": "array",
            "description": "Limitations or caveats for this comparative analysis",
            "items": {
                "type": "string"
            },
            "maxItems": 3
        }
    }
}

# This prompt template is used by the comparative analysis function
COMPARATIVE_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert in media analysis specializing in comparative news coverage. Your task is to analyze how different sources cover the same news story, focusing on differences in framing, emphasis, included/excluded information, and apparent source interests.

I'll provide you with information about multiple articles from different sources that cover the same news story. Review this information carefully and create a detailed analysis of how coverage differs across sources.

RELATED ARTICLES COVERING THE SAME STORY:
{articles_json}

Examine these articles collectively, analyzing how different sources present the same core story. Focus on these key areas:

1. STORY CORE FACTS
   * What core facts/events are consistently reported across all sources?
   * Which key entities appear in all or most articles?
   * What details are consistently included regardless of source?

2. SOURCE DIFFERENCES
   * For each source, identify:
     - Its distinctive focus or emphasis
     - Its unique angle or perspective
     - Entities mentioned only by this source
     - What seems most important to this source based on emphasis and placement

3. INFORMATION GAPS
   * Identify important information that appears in some sources but not others:
     - Each significant information item
     - Which sources include it
     - Which sources omit it
     - Why this information gap matters (adds critical context, offers alternative perspective, etc.)

4. FRAMING COMPARISON
   * Analyze how sources frame the same story differently across these dimensions:
     - How responsibility or blame is attributed
     - How the core problem is defined
     - Moral evaluations presented
     - Solutions proposed
     - Emphasis on conflict
     - Economic vs. human impact
     - Political implications
   * Identify the dominant narrative across sources
   * Note any counter-narratives presented by particular sources

5. LANGUAGE ANALYSIS
   * Compare tone variations across sources (alarmist, reassuring, clinical, empathetic, etc.)
   * Identify emotionally charged language or terminology used by each source

6. SOURCE INTERESTS
   * Based on coverage patterns, what does each source seem most interested in?
   * What possible motivations might explain each source's approach to coverage?

7. ANALYSIS LIMITATIONS
   * Note important limitations or caveats for your comparative analysis

Provide your comprehensive analysis as a JSON object following the exact structure defined in the schema. Be objective, evidence-based, and avoid introducing your own biases.
"""

async def analyze_and_enrich_article(article: Article) -> Article:
    """Analyzes a single article using LLMService and enriches it."""
    if not article.summary and not article.title:
        logger.warning(f"Article {article.url} has no summary or title for LLM analysis, skipping.")
        return article

    # Prefer summary, fallback to title for analysis content
    content_to_analyze = article.summary if article.summary else article.title

    if llm_service.client: # Check if LLM client is available
        logger.info(f"Analyzing article with LLM: {article.url}")
        try:
            # Use the JSON schema for more controlled response formatting
            analysis_result = await llm_service.analyze_content(
                content=content_to_analyze,
                prompt_template=TRIAGE_PROMPT_TEMPLATE,
                model=settings.TRIAGE_LLM_MODEL_NAME or settings.DEFAULT_LLM_MODEL_NAME,
                json_schema=TRIAGE_JSON_SCHEMA
            )
            if analysis_result and isinstance(analysis_result, dict) and 'analysis_text' in analysis_result:
                raw_text_response = analysis_result.get('analysis_text')
                # Attempt to parse the text response as JSON
                import json
                try:
                    # Check if raw_text_response is not None or empty before trying to parse it
                    if raw_text_response is None or not raw_text_response.strip():
                        logger.error(f"Raw text response is empty or None for {article.url}")
                        article.llm_analysis_raw_response = {"error": "Empty response from LLM"}
                        return article  # Return the original article without modifications
                    
                    # For schema validation errors, handle differently
                    if analysis_result.get('schema_error'):
                        logger.error(f"JSON schema validation error for {article.url}: {analysis_result.get('error')}")
                        article.llm_analysis_raw_response = {
                            "error": "Schema validation error",
                            "details": analysis_result.get('error')
                        }
                        return article
                        
                    parsed_llm_data = json.loads(raw_text_response)
                    article.llm_category = parsed_llm_data.get("category")
                    article.llm_sentiment = parsed_llm_data.get("sentiment")
                    article.llm_key_claim = parsed_llm_data.get("key_claim")
                    article.llm_requires_deep_analysis = str(parsed_llm_data.get("requires_deep_analysis")).lower() == 'yes'
                    # Store keywords for finding related articles
                    article.llm_keywords = parsed_llm_data.get("keywords", [])
                    # Extract entities if present
                    main_entities = parsed_llm_data.get("main_entities", [])
                    if main_entities and isinstance(main_entities, list):
                        # Only store the entity names (strings) in llm_entities for model compatibility
                        entity_names = []
                        for entity in main_entities:
                            if isinstance(entity, dict) and "text" in entity:
                                entity_names.append(entity["text"])
                            elif isinstance(entity, str):
                                entity_names.append(entity)
                        article.llm_entities = entity_names
                    article.llm_analysis_raw_response = parsed_llm_data # Store the parsed JSON
                    logger.info(f"LLM analysis successful for {article.url}: Category: {article.llm_category}, Sentiment: {article.llm_sentiment}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse LLM response as JSON for {article.url}: {raw_text_response}")
                    article.llm_analysis_raw_response = {"error": "JSONDecodeError", "raw_text": raw_text_response}
                except Exception as e:
                    logger.error(f"Error processing LLM JSON response for {article.url}: {e}", exc_info=True)
                    article.llm_analysis_raw_response = {"error": str(e), "raw_text": raw_text_response}
            elif analysis_result:
                logger.warning(f"LLM analysis for {article.url} did not return expected dict structure: {analysis_result}")
                article.llm_analysis_raw_response = analysis_result # Store whatever was returned
            else:
                logger.warning(f"LLM analysis returned no result for {article.url}")

        except Exception as e:
            logger.error(f"Error during LLM analysis for article {article.url}: {e}", exc_info=True)
            article.llm_analysis_raw_response = {"error": f"LLM analysis failed: {str(e)}"}
    else:
        logger.info(f"LLM client not available. Skipping LLM analysis for article: {article.url}")
    return article

async def perform_deep_article_analysis(article_id: str) -> Optional[Article]:
    """
    Performs deep analysis on a specific article using LLMService and updates it in the DB.
    Returns the updated article or None if not found or analysis fails.
    """
    collection = await get_article_collection()
    try:
        # In pymongo, ObjectId needs to be imported and used for querying by _id
        from bson import ObjectId
        if not ObjectId.is_valid(article_id):
            logger.error(f"Invalid article_id format: {article_id}")
            return None
        article_doc = await collection.find_one({"_id": ObjectId(article_id)})
    except Exception as e:
        logger.error(f"Error fetching article {article_id} for deep analysis: {e}", exc_info=True)
        return None

    if not article_doc:
        logger.warning(f"Article {article_id} not found for deep analysis.")
        return None

    # Convert DB doc to Pydantic model
    article_doc["id"] = str(article_doc["_id"])
    # Fix llm_entities if it's a list of dicts (convert to list of strings)
    if "llm_entities" in article_doc and isinstance(article_doc["llm_entities"], list):
        if article_doc["llm_entities"] and isinstance(article_doc["llm_entities"][0], dict):
            article_doc["llm_entities"] = [e.get("text", "") for e in article_doc["llm_entities"] if isinstance(e, dict) and "text" in e]
    article = Article(**article_doc)

    if not article.summary and not article.title and not article.content:
        logger.warning(f"Article {article.url} has no content (summary, title, or content field) for deep LLM analysis, skipping.")
        return article # Return article as is, no analysis performed

    # Prefer content field if available for deep analysis, then summary, then title
    content_to_analyze = article.content or article.summary or article.title

    if llm_service.client:
        logger.info(f"Performing DEEP analysis with LLM for article: {article.url}")
        try:
            analysis_result = await llm_service.analyze_content(
                content=content_to_analyze,
                prompt_template=DEEP_ANALYSIS_PROMPT_TEMPLATE,
                model=settings.DEEP_ANALYSIS_LLM_MODEL_NAME, # Use specific deep analysis model
                max_tokens=1000, # Allow more tokens for detailed analysis
                temperature=0.2, # Lower temperature for more factual/deterministic output
                json_schema=DEEP_ANALYSIS_JSON_SCHEMA
            )

            if analysis_result and isinstance(analysis_result, dict) and 'analysis_text' in analysis_result:
                raw_text_response = analysis_result.get('analysis_text')
                import json
                
                # Check for schema validation errors first
                if analysis_result.get('schema_error'):
                    logger.error(f"JSON schema validation error in deep analysis for {article.url}: {analysis_result.get('error')}")
                    article.llm_deep_analysis_results = {
                        "error": "Schema validation error",
                        "details": analysis_result.get('error')
                    }
                    await collection.update_one(
                        {"_id": ObjectId(article.id)}, 
                        {"$set": {"llm_deep_analysis_results": article.llm_deep_analysis_results}}
                    )
                    return article
                
                try:
                    parsed_llm_data = json.loads(raw_text_response)
                    article.llm_deep_analysis_results = parsed_llm_data
                    logger.info(f"Deep LLM analysis successful for {article.url}. Stored in llm_deep_analysis_results.")
                    
                    # Update the article in the database
                    update_result = await collection.update_one(
                        {"_id": ObjectId(article.id)},
                        {"$set": {"llm_deep_analysis_results": article.llm_deep_analysis_results}}
                    )
                    if update_result.modified_count == 0 and update_result.matched_count > 0:
                        logger.info(f"Deep analysis data for {article.url} was the same as existing data.")
                    elif update_result.modified_count == 0:
                        logger.warning(f"Failed to update article {article.url} with deep analysis results (no document matched).")
                    else:
                        logger.info(f"Article {article.url} updated successfully with deep analysis results.")
                    return article # Return the updated article model

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse deep LLM response as JSON for {article.url}: {raw_text_response}")
                    # Optionally store the raw error
                    article.llm_deep_analysis_results = {"error": "JSONDecodeError", "raw_text": raw_text_response}
                    await collection.update_one({"_id": ObjectId(article.id)}, {"$set": {"llm_deep_analysis_results": article.llm_deep_analysis_results}})
                except Exception as e:
                    logger.error(f"Error processing deep LLM JSON response for {article.url}: {e}", exc_info=True)
                    article.llm_deep_analysis_results = {"error": str(e), "raw_text": raw_text_response}
                    await collection.update_one({"_id": ObjectId(article.id)}, {"$set": {"llm_deep_analysis_results": article.llm_deep_analysis_results}})
            elif analysis_result:
                logger.warning(f"Deep LLM analysis for {article.url} did not return expected dict structure: {analysis_result}")
                article.llm_deep_analysis_results = analysis_result
                await collection.update_one({"_id": ObjectId(article.id)}, {"$set": {"llm_deep_analysis_results": article.llm_deep_analysis_results}})
            else:
                logger.warning(f"Deep LLM analysis returned no result for {article.url}")
                return article # Return article as is, no analysis performed

        except Exception as e:
            logger.error(f"Error during deep LLM analysis for article {article.url}: {e}", exc_info=True)
            # Optionally store error in the article object if desired, even if it's not saved here
            return article # Return article as is
    else:
        logger.info(f"LLM client not available. Skipping deep LLM analysis for article: {article.url}")
    
    return article # Return article, possibly unmodified if LLM client wasn't available

async def triage_new_articles(limit: int = 1000) -> Dict[str, int]:
    """
    Finds articles that haven't had initial triage analysis and performs it.
    Saves each article's analysis result as it's processed.
    Identifies and links articles that refer to the same news story.
    Returns a count of analyzed, failed, and linked articles.
    """
    collection = await get_article_collection()
    unanalyzed_cursor = collection.find({
        "$or": [
            {"llm_category": {"$exists": False}},
            {"llm_category": None}
        ]
    }).limit(limit)

    analyzed_count = 0
    failed_analysis_count = 0
    linked_article_count = 0

    async for article_doc in unanalyzed_cursor: # Motor cursor is already async iterable
        article_doc["id"] = str(article_doc["_id"])
        # Fix llm_entities if it's a list of dicts (convert to list of strings)
        if "llm_entities" in article_doc and isinstance(article_doc["llm_entities"], list):
            if article_doc["llm_entities"] and isinstance(article_doc["llm_entities"][0], dict):
                article_doc["llm_entities"] = [e.get("text", "") for e in article_doc["llm_entities"] if isinstance(e, dict) and "text" in e]
        # Add source_type if it's missing
        if "source_type" not in article_doc:
            article_doc["source_type"] = "db"  # Default source_type for articles from the database
        article = Article(**article_doc)

        logger.info(f"Performing triage analysis for article: {article.url}")
        enriched_article = await analyze_and_enrich_article(article)

        update_data = {}
        if enriched_article.llm_analysis_raw_response and not enriched_article.llm_analysis_raw_response.get("error"):
            analyzed_count += 1
            update_data = {
                "llm_category": enriched_article.llm_category,
                "llm_sentiment": enriched_article.llm_sentiment,
                "llm_key_claim": enriched_article.llm_key_claim,
                "llm_requires_deep_analysis": enriched_article.llm_requires_deep_analysis,
                "llm_keywords": enriched_article.llm_keywords,
                "llm_entities": enriched_article.llm_entities,
                "llm_analysis_raw_response": enriched_article.llm_analysis_raw_response,
                "last_llm_triage_at": enriched_article.fetched_date # Or use current datetime
            }
            
            # Find and link related articles
            try:
                # Save triage data first to make article searchable for relationships
                await collection.update_one({"_id": article_doc["_id"]}, {"$set": update_data})
                
                # Set ID for the article to allow relationship building
                enriched_article.id = str(article_doc["_id"])
                
                # Find and link related articles
                logger.info(f"Finding related articles for: {article.url}")
                related_ids = await find_and_link_related_articles(enriched_article)
                
                if related_ids:
                    linked_article_count += len(related_ids)
                    logger.info(f"Found {len(related_ids)} related articles for {article.url}")
                    # Update article with related ids
                    await collection.update_one(
                        {"_id": article_doc["_id"]},
                        {"$set": {"related_article_ids": related_ids}}
                    )
            except Exception as e:
                logger.error(f"Error finding related articles for {article.url}: {e}", exc_info=True)
                
            logger.info(f"Triage analysis successful for article: {article.url}")
        else:
            failed_analysis_count +=1
            logger.warning(f"Triage analysis failed or yielded error for article: {article.url}")
            update_data = {"llm_triage_status": "failed"}

        # For articles where analysis failed, we still need to update the status
        if not enriched_article.llm_analysis_raw_response or enriched_article.llm_analysis_raw_response.get("error"):
            try:
                result = await collection.update_one({"_id": article_doc["_id"]}, {"$set": update_data})
                if result.modified_count == 0 and result.matched_count > 0:
                    logger.info(f"Article {article.url} triage status was the same as existing data or not modified.")
                elif result.modified_count == 0:
                    logger.warning(f"Failed to update article {article.url} with triage results (no document matched or no change made). ObjectId: {article_doc['_id']}")
            except Exception as e:
                logger.error(f"Error updating article {article.url} after triage: {e}", exc_info=True)
                failed_analysis_count += 1 # Count as failed if DB update fails


    logger.info(f"Triage analysis completed. Analyzed: {analyzed_count}, Failed: {failed_analysis_count}, Linked: {linked_article_count}")
    return {"analyzed": analyzed_count, "failed": failed_analysis_count, "linked": linked_article_count}

async def save_articles(articles: List[Article]) -> Dict[str, int]:
    """
    Saves a list of Article objects to the database without performing LLM analysis.
    Performs an upsert operation based on the article URL to avoid duplicates.
    Returns a dictionary with counts of inserted and updated articles.
    """
    if not articles:
        return {"inserted": 0, "updated": 0, "failed": 0}

    collection = await get_article_collection()
    operations = []
    processed_urls = set() # To handle potential duplicates within the input list

    for article in articles: # Changed from enriched_articles to articles
        if str(article.url) in processed_urls: # Ensure URL is string for set comparison
            logger.warning(f"Duplicate URL in input list, skipping: {article.url}")
            continue
        processed_urls.add(str(article.url))

        # Convert Pydantic model to dict, excluding 'id' if None, as MongoDB will generate _id
        # Pydantic v2: model_dump(), Pydantic v1: dict()
        try:
            article_dict = article.model_dump(exclude_none=True, exclude={'id'}) 
        except:
            article_dict = article.dict(exclude_none=True, exclude={'id'}) # Fallback for Pydantic v1
        
        # Ensure HttpUrl is converted to string for MongoDB
        if 'url' in article_dict and hasattr(article_dict['url'], 'unicode_string'): # Check if it's a PydanticUrl
            article_dict['url'] = str(article_dict['url'])
        elif 'url' in article_dict and not isinstance(article_dict['url'], str):
             # Fallback for other URL-like objects, though HttpUrl is primary concern
            article_dict['url'] = str(article_dict['url'])

        # If article.id is provided and is a valid ObjectId string, you might want to use it as _id.
        # For now, we let MongoDB generate _id.

        op = UpdateOne(
            {"url": str(article.url)},  # Filter by URL (ensure URL is string)
            {
                "$set": article_dict,
                "$setOnInsert": {"first_seen_at": article.fetched_date} # Record when it was first added
            },
            upsert=True
        )
        operations.append(op)

    if not operations:
        return {"inserted": 0, "updated": 0, "failed": 0}

    try:
        result = await collection.bulk_write(operations, ordered=False)
        inserted_count = result.upserted_count
        updated_count = result.modified_count
        logger.info(f"Saved articles to DB. Inserted: {inserted_count}, Updated: {updated_count}")
        return {"inserted": inserted_count, "updated": updated_count, "failed": 0}
    except Exception as e:
        logger.error(f"Error saving articles to DB: {e}", exc_info=True)
        return {"inserted": 0, "updated": 0, "failed": len(operations)}

async def list_articles(skip: int = 0, limit: int = 20) -> List[Article]:
    """
    Retrieves a paginated list of articles from the database,
    sorted by publication_date (descending), then fetched_date (descending).
    """
    collection = await get_article_collection()
    articles_from_db_cursor = collection.find().sort([
        ("publication_date", DESCENDING),
        ("fetched_date", DESCENDING)
    ]).skip(skip).limit(limit)
    
    articles_from_db = []
    async for doc in articles_from_db_cursor: # Motor cursor is async iterable
        doc["id"] = str(doc["_id"]) # Map MongoDB's _id to Pydantic's id field
        # Fix llm_entities if it's a list of dicts (convert to list of strings)
        if "llm_entities" in doc and isinstance(doc["llm_entities"], list):
            if doc["llm_entities"] and isinstance(doc["llm_entities"][0], dict):
                doc["llm_entities"] = [e.get("text", "") for e in doc["llm_entities"] if isinstance(e, dict) and "text" in e]
        # Ensure all fields are present or provide defaults if necessary before creating Article model
        # This is important if new optional fields were added to the model but are not in older DB documents
        articles_from_db.append(Article(**doc))

    logger.info(f"Retrieved {len(articles_from_db)} articles from DB (skip={skip}, limit={limit})")
    return articles_from_db

async def find_and_link_related_articles(article: Article) -> List[str]:
    """
    Finds articles that are related to the given article, focusing on articles covering the same news story.
    
    Employs multiple criteria to determine if articles are about the same news story:
    - Similar keywords and entities (content similarity)
    - Publication date proximity (articles published within a short timespan)
    - Title similarity (using key terms in titles)
    - Category match
    - Source diversity (to avoid just grouping articles from the same source)
    
    Updates both the current article and related articles with bidirectional relationships.
    Returns a list of ids of the related articles.
    """
    if not article.llm_keywords and not article.llm_entities and not article.title:
        logger.warning(f"Article {article.id} has insufficient metadata to find related articles")
        return []
    
    collection = await get_article_collection()
    query = {"_id": {"$ne": ObjectId(article.id)}}  # Exclude the current article using ObjectId
    
    # Build the query based on available metadata
    conditions = []
    
    # Match by keywords if available (strong indicator of same story)
    if article.llm_keywords:
        # Need multiple matching keywords to indicate same story
        keyword_condition = {"$expr": {"$gte": [{"$size": {"$setIntersection": ["$llm_keywords", article.llm_keywords]}}, 2]}}
        conditions.append(keyword_condition)
    
    # Match by entities if available (e.g., same people, organizations, locations)
    if article.llm_entities:
        entity_texts = [entity["text"] for entity in article.llm_entities]
        if entity_texts:
            # Require multiple matching entities for same story
            entity_condition = {"$expr": {"$gte": [{"$size": {"$setIntersection": [{"$map": {"input": "$llm_entities", "in": "$$this.text"}}, entity_texts]}}, 2]}}
            conditions.append(entity_condition)
    
    # Match by category - same stories should be in the same category
    if article.llm_category:
        conditions.append({"llm_category": article.llm_category})
    
    # Match by publication date proximity - same stories are usually published within a short timespan
    # Include articles published within 3 days before or after this article
    if article.publication_date:
        date_condition = {
            "publication_date": {
                "$gte": article.publication_date - timedelta(days=3),
                "$lte": article.publication_date + timedelta(days=3)
            }
        }
        conditions.append(date_condition)
    
    # Match by key claim similarity - articles covering the same story often make similar key claims
    if article.llm_key_claim:
        # Skip text search which can cause complex query issues
        # Instead, always use regex for key claim matching which is more compatible with other query operators
        if len(article.llm_key_claim) > 5:  # Only use if key claim is substantial
            # Extract significant words from key claim (avoid stop words)
            words = article.llm_key_claim.lower().split()
            stop_words = {"the", "a", "an", "and", "in", "on", "at", "to", "for", "with", "by", "of", "is", "are", "that", "this", "it", "as"}
            significant_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            # Use the most significant words (up to 3) for regex matching
            if significant_words:
                significant_terms = significant_words[:3]
                regex_patterns = []
                for term in significant_terms:
                    # Escape special regex chars and create case-insensitive pattern
                    regex_patterns.append({"llm_key_claim": {"$regex": re.escape(term), "$options": "i"}})
                if regex_patterns:
                    conditions.append({"$or": regex_patterns})
    
    # Combine conditions with OR to find potential matches
    if conditions:
        query["$or"] = conditions
    
    # Find potential related articles
    related_article_ids = []
    update_operations = []
    seen_sources = set([article.source_name]) if article.source_name else set()
    
    try:
        # Check if the query might be too complex and simplify if needed
        if len(query.get("$or", [])) > 3:
            logger.info(f"Complex query detected for article {article.id}, simplifying to ensure execution")
            # Keep only the most relevant conditions (keywords and category)
            simplified_conditions = []
            for condition in query.get("$or", []):
                # Prioritize keeping keyword conditions as they're most relevant
                if "$expr" in condition and "llm_keywords" in str(condition):
                    simplified_conditions.append(condition)
                # Keep category condition as it's simple and effective
                elif "llm_category" in condition:
                    simplified_conditions.append(condition)
                    
            # Ensure we have at least some conditions
            if simplified_conditions:
                query["$or"] = simplified_conditions[:3]  # Keep at most 3 conditions
            else:
                # If no good conditions found, fall back to just category and exclude current article
                query = {"_id": {"$ne": ObjectId(article.id)}}
                if article.llm_category:
                    query["llm_category"] = article.llm_category
        
        cursor = collection.find(query, {
            "_id": 1, 
            "title": 1, 
            "llm_keywords": 1, 
            "llm_entities": 1, 
            "llm_category": 1,
            "publication_date": 1,
            "source_name": 1,
            "llm_key_claim": 1
        })
        
        # For each potential match, calculate a similarity score
        async for related_doc in cursor:
            related_id = str(related_doc["_id"])
            
            # Skip if we already have enough related articles
            if len(related_article_ids) >= 10:
                break
            
            # Advanced scoring: consider multiple factors to determine if articles cover the same story
            score = 0
            
            # Score for matching keywords
            if article.llm_keywords and "llm_keywords" in related_doc:
                related_keywords = related_doc.get("llm_keywords", [])
                overlapping_keywords = set(article.llm_keywords) & set(related_keywords)
                score += len(overlapping_keywords) * 2  # Weight keywords higher
            
            # Score for matching entities
            if article.llm_entities and "llm_entities" in related_doc:
                article_entity_texts = [entity["text"] for entity in article.llm_entities]
                related_entity_texts = [entity["text"] for entity in related_doc.get("llm_entities", [])]
                overlapping_entities = set(article_entity_texts) & set(related_entity_texts)
                score += len(overlapping_entities) * 3  # Weight entities even higher
            
            # Score for category match
            if article.llm_category and related_doc.get("llm_category") == article.llm_category:
                score += 1
            
            # Score for publication date proximity
            if article.publication_date and related_doc.get("publication_date"):
                delta = abs((article.publication_date - related_doc["publication_date"]).total_seconds())
                if delta < 86400:  # Same day
                    score += 2
                elif delta < 172800:  # Within 2 days
                    score += 1
            
            # Source diversity bonus - prefer articles from different sources covering the same story
            source_name = related_doc.get("source_name")
            if source_name and source_name not in seen_sources:
                score += 1
                seen_sources.add(source_name)
            
            # Score for title similarity (basic version - could be enhanced with text similarity algorithms)
            if article.title and "title" in related_doc:
                # Simple text matching - count matching significant words
                article_title_words = set(article.title.lower().split())
                related_title_words = set(related_doc["title"].lower().split())
                
                # Remove common stop words that don't help identify topic similarity
                stop_words = {"the", "a", "an", "and", "in", "on", "at", "to", "for", "with", "by", "of", "is", "are"}
                article_title_words = article_title_words - stop_words
                related_title_words = related_title_words - stop_words
                
                overlapping_words = article_title_words & related_title_words
                if len(overlapping_words) >= 3:  # At least 3 significant words in common
                    score += 2
            
            # If the score meets our threshold, consider it related to the same news story
            if score >= 5:  # Higher threshold to ensure articles are about the same story
                related_article_ids.append(related_id)
                
                # Create update operation to add current article ID to the related article's related_article_ids
                update_operations.append(
                    UpdateOne(
                        {"_id": related_doc["_id"]},
                        {"$addToSet": {"related_article_ids": article.id}}
                    )
                )
    except Exception as e:
        logger.error(f"Error finding related articles for {article.id}: {e}", exc_info=True)
        
        # Simple fallback query - just match on category
        try:
            logger.info(f"Attempting fallback query for article {article.id}")
            
            # Very simple query - just match on category and exclude current article
            simple_query = {"_id": {"$ne": ObjectId(article.id)}}
            if article.llm_category:
                simple_query["llm_category"] = article.llm_category
                
                # Try to find at least a few articles in the same category
                cursor = collection.find(simple_query).limit(5)
                
                async for related_doc in cursor:
                    related_id = str(related_doc["_id"])
                    related_article_ids.append(related_id)
                    
                    # Create update operation to add current article ID to the related article's related_article_ids
                    update_operations.append(
                        UpdateOne(
                            {"_id": related_doc["_id"]},
                            {"$addToSet": {"related_article_ids": article.id}}
                        )
                    )
                    
                if related_article_ids:
                    logger.info(f"Found {len(related_article_ids)} articles in the same category for {article.id}")
        except Exception as e:
            logger.error(f"Fallback query for article {article.id} also failed: {e}", exc_info=True)
    
    # Update all related articles in a single bulk operation
    if update_operations:
        try:
            result = await collection.bulk_write(update_operations)
            logger.info(f"Updated {result.modified_count} articles with relationship to article {article.id}")
        except Exception as e:
            logger.error(f"Error updating related articles for {article.id}: {e}", exc_info=True)
    
    return related_article_ids

async def update_related_articles_for_existing(limit: int = 100, days_back: int = 30) -> Dict[str, int]:
    """
    Process existing articles to find and update their related articles.
    This is useful for a one-time run when the related_article_ids feature is first introduced.
    
    Args:
        limit: Maximum number of articles to process
        days_back: Only process articles from the last X days
        
    Returns:
        Dictionary with counts of processed and linked articles
    """
    collection = await get_article_collection()
    
    # Get articles from the last days_back days that have been processed by LLM (have keywords)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    query = {
        "fetched_date": {"$gte": cutoff_date},
        "llm_keywords": {"$exists": True, "$ne": []},
        "$or": [
            {"related_article_ids": {"$exists": False}},
            {"related_article_ids": []}
        ]
    }
    
    cursor = collection.find(query).sort("fetched_date", DESCENDING).limit(limit)
    
    processed_count = 0
    linked_article_count = 0
    
    async for article_doc in cursor:
        article_doc["id"] = str(article_doc["_id"])
        # Fix llm_entities if it's a list of dicts (convert to list of strings)
        if "llm_entities" in article_doc and isinstance(article_doc["llm_entities"], list):
            if article_doc["llm_entities"] and isinstance(article_doc["llm_entities"][0], dict):
                article_doc["llm_entities"] = [e.get("text", "") for e in article_doc["llm_entities"] if isinstance(e, dict) and "text" in e]
        article = Article(**article_doc)
        
        logger.info(f"Finding related articles for: {article.url}")
        related_ids = await find_and_link_related_articles(article)
        
        if related_ids:
            linked_article_count += len(related_ids)
            logger.info(f"Found {len(related_ids)} related articles for {article.url}")
            # Update article with related ids
            await collection.update_one(
                {"_id": article_doc["_id"]},
                {"$set": {"related_article_ids": related_ids}}
            )
        
        processed_count += 1
    
    logger.info(f"Update of existing articles completed. Processed: {processed_count}, Linked: {linked_article_count}")
    return {"processed": processed_count, "linked": linked_article_count}

async def get_related_articles(article_id: str) -> List[Article]:
    """
    Retrieves all articles that are related to the same news story as the given article.
    
    Args:
        article_id: The ID of the article to find related stories for
        
    Returns:
        List of Article objects that cover the same news story
    """
    collection = await get_article_collection()
    
    # First, get the article to check its related_article_ids
    try:
        if not ObjectId.is_valid(article_id):
            logger.warning(f"Invalid article_id format: {article_id}")
            return []
        article_doc = await collection.find_one({"_id": ObjectId(article_id)})
    except Exception as e:
        logger.error(f"Error fetching article {article_id} for related articles: {e}", exc_info=True)
        return []
    
    # If no related articles, return empty list
    if not article_doc or "related_article_ids" not in article_doc or not article_doc["related_article_ids"]:
        logger.info(f"No related articles found for article_id: {article_id}")
        return []
    
    # Convert string IDs to ObjectIds for MongoDB query
    related_article_object_ids = [ObjectId(related_id) for related_id in article_doc["related_article_ids"] if ObjectId.is_valid(related_id)]
    
    # Get all related articles in a single query
    if related_article_object_ids:
        related_articles_cursor = collection.find({"_id": {"$in": related_article_object_ids}})
        related_articles = []
        async for doc in related_articles_cursor:
            doc["id"] = str(doc["_id"])
            # Fix llm_entities if it's a list of dicts (convert to list of strings)
            if "llm_entities" in doc and isinstance(doc["llm_entities"], list):
                if doc["llm_entities"] and isinstance(doc["llm_entities"][0], dict):
                    doc["llm_entities"] = [e.get("text", "") for e in doc["llm_entities"] if isinstance(e, dict) and "text" in e]
            related_articles.append(Article(**doc))
        return related_articles
    
    return []

async def perform_comparative_analysis(article_ids: List[str]) -> Dict[str, Any]:
    """
    Performs a comparative analysis on a set of related articles from different sources.
    Identifies differences in coverage, framing, emphasis, and source interests.
    
    Args:
        article_ids: List of article IDs to compare (should be about the same story)
        
    Returns:
        Dictionary containing the comparative analysis results
    """
    if len(article_ids) < 2:
        logger.warning("Comparative analysis requires at least 2 articles")
        return {"error": "Insufficient articles for comparison", "article_count": len(article_ids)}
    
    # Get full article objects for all provided IDs
    collection = await get_article_collection()
    object_ids = [ObjectId(aid) for aid in article_ids if ObjectId.is_valid(aid)]
    
    if len(object_ids) < 2:
        logger.warning("Not enough valid article IDs for comparison")
        return {"error": "Not enough valid article IDs", "valid_ids": len(object_ids)}
    
    # Retrieve all articles in a single query
    articles = []
    async for doc in collection.find({"_id": {"$in": object_ids}}):
        doc["id"] = str(doc["_id"])
        # Fix llm_entities if it's a list of dicts (convert to list of strings)
        if "llm_entities" in doc and isinstance(doc["llm_entities"], list):
            if doc["llm_entities"] and isinstance(doc["llm_entities"][0], dict):
                doc["llm_entities"] = [e.get("text", "") for e in doc["llm_entities"] if isinstance(e, dict) and "text" in e]
        articles.append(Article(**doc))
    
    if len(articles) < 2:
        logger.warning(f"Could only retrieve {len(articles)} articles for comparative analysis")
        return {"error": "Could not retrieve enough articles", "retrieved": len(articles)}
    
    logger.info(f"Performing comparative analysis on {len(articles)} articles")
    
    # Prepare article data for the LLM
    article_summaries = []
    for article in articles:
        # Use most complete content available for each article
        content = article.content or article.summary or article.title
        
        # Prepare a summary of the article for the LLM to analyze
        article_summary = {
            "source_name": article.source_name,
            "title": article.title,
            "publication_date": article.publication_date.isoformat() if article.publication_date else None,
            "content": content[:2000] if content else None,  # Limit content length to avoid token limits
            "llm_category": article.llm_category,
            "llm_sentiment": article.llm_sentiment,
            "llm_key_claim": article.llm_key_claim,
            "llm_keywords": article.llm_keywords,
            "llm_entities": article.llm_entities,
            "url": str(article.url)
        }
        article_summaries.append(article_summary)
    
    # Convert article summaries to JSON for the prompt
    articles_json = json.dumps(article_summaries, indent=2)
    
    # Perform LLM analysis
    if llm_service.client:
        try:
            analysis_result = await llm_service.analyze_content(
                content=articles_json,
                prompt_template=COMPARATIVE_ANALYSIS_PROMPT_TEMPLATE,
                model=settings.DEFAULT_LLM_MODEL_NAME,
                max_tokens=2500,  # Comparative analysis needs more tokens
                temperature=0.2,  # Lower temperature for more consistent analysis
                json_schema=COMPARATIVE_ANALYSIS_JSON_SCHEMA
            )
            
            if analysis_result and isinstance(analysis_result, dict) and 'analysis_text' in analysis_result:
                # Parse the LLM response
                try:
                    comparative_analysis = json.loads(analysis_result['analysis_text'])
                    logger.info("Successfully performed comparative analysis")
                    
                    # Store the analysis in the database linked to these articles
                    analysis_record = {
                        "article_ids": article_ids,
                        "analysis_results": comparative_analysis,
                        "created_at": datetime.now(timezone.utc),
                        "type": "comparative_analysis"
                    }
                    
                    # Store in a separate collection for analyses
                    db = collection.database
                    analyses_collection = db.analyses
                    insert_result = await analyses_collection.insert_one(analysis_record)
                    analysis_id = str(insert_result.inserted_id)
                    
                    # Update all involved articles with a reference to the comparative analysis
                    update_operations = []
                    for aid in article_ids:
                        update_operations.append(
                            UpdateOne(
                                {"_id": ObjectId(aid)},
                                {"$set": {"comparative_analysis_id": analysis_id}}
                            )
                        )
                    
                    # Use bulk update for better performance
                    if update_operations:
                        bulk_result = await collection.bulk_write(update_operations)
                        logger.info(f"Updated {bulk_result.modified_count} articles with comparative analysis ID {analysis_id}")
                    
                    return {
                        "comparative_analysis": comparative_analysis, 
                        "article_count": len(articles),
                        "analysis_id": analysis_id
                    }
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse comparative analysis response as JSON: {e}", exc_info=True)
                    return {"error": "Failed to parse LLM response", "raw_response": analysis_result.get('analysis_text', '')}
            else:
                logger.warning(f"LLM comparative analysis didn't return expected structure: {analysis_result}")
                return {"error": "Invalid LLM response structure", "raw_response": analysis_result}
                
        except Exception as e:
            logger.error(f"Error during comparative analysis: {e}", exc_info=True)
            return {"error": f"Analysis failed: {str(e)}"}
    else:
        logger.warning("LLM client not available for comparative analysis")
        return {"error": "LLM service unavailable"}
    
async def get_comparative_analysis_for_article(article_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the comparative analysis associated with an article.
    
    Args:
        article_id: ID of the article to get comparative analysis for
        
    Returns:
        Dictionary containing the comparative analysis results or None if not found
    """
    if not ObjectId.is_valid(article_id):
        logger.warning(f"Invalid article_id format: {article_id}")
        return None
    
    collection = await get_article_collection()
    
    try:
        # Fetch the article to get its comparative analysis ID
        article_doc = await collection.find_one(
            {"_id": ObjectId(article_id)}, 
            {"comparative_analysis_id": 1}
        )
        
        if not article_doc or "comparative_analysis_id" not in article_doc or not article_doc["comparative_analysis_id"]:
            logger.info(f"No comparative analysis ID found for article {article_id}")
            return None
        
        # Fetch the analysis from the analyses collection
        analyses_collection = collection.database.analyses
        analysis_doc = await analyses_collection.find_one({"_id": ObjectId(article_doc["comparative_analysis_id"])})
        
        if not analysis_doc:
            logger.warning(f"Comparative analysis {article_doc['comparative_analysis_id']} referenced by article {article_id} not found")
            return None
        
        # Return the analysis results
        return {
            "comparative_analysis": analysis_doc["analysis_results"],
            "article_ids": analysis_doc["article_ids"],
            "created_at": analysis_doc["created_at"],
            "analysis_id": str(analysis_doc["_id"])
        }
    
    except Exception as e:
        logger.error(f"Error retrieving comparative analysis for article {article_id}: {e}", exc_info=True)
        return None
