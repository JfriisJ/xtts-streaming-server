# Global Software Engineering: Evolution and Trends
 # Abstract
 
Abstract—Professional software products and IT systems and
services today are developed mostly by globally distributed
teams, projects, and companies. Successfully orchestrating Global
Software Engineering (GSE) has become the major success
factor both for organizations and practitioners. Yet, more than
a half of all distributed projects does not achieve the intended
objectives and is canceled. This paper summarizes experiences
from academia and industry in a way to facilitate knowledge
and technology transfer. It is based on an evaluation of 10 years
of research, and industry collaboration and experience reported
at the IEEE International Conference on Software Engineering
(ICGSE) series. The outcomes of our analysis show GSE as a
field highly attached to industry and, thus, a considerable share
of ICGSE papers address the transfer of Software Engineering
concepts and solutions to the global stage. We found collaboration
and teams, processes and organization, sourcing and supplier
management, and success factors to be the topics gaining the most
interest of researchers and practitioners. Beyond the analysis of
the past conferences, we also look at current trends in GSE to
motivate further research and industrial collaboration.
Index Terms—global software engineering; GSE; near-shoring;
outsourcing; offshoring; longitudinal study; ICGSE
 
 
 # I. INTRODUCTION
Today, hardly any software product or IT service is devel-
oped at only one place or by only one team. Software like
all industry products is the result of complex multinational
supply chains that include many partners from conceptu-
alization over development and production to maintenance.
Successfully managing global software projects has rapidly
become key across industries. However, a considerable share
of those global projects does not meet the expectations  ,  .
Traditional labor-cost-based location decisions are replaced by
systematic improvements of business processes in a distributed
context. As we captured at the recentIEEE International
Conference on Software Engineering(ICGSE;  ), benefits
are tangible: better multi-site collaboration, clear supplier
agreements, and transparent interfaces are the most often
reported benefits.
In the past decade, Global Software Engineering (GSE),
IT outsourcing, and business process outsourcing have shown
growth rates of 10-20% per annum  ,  ,  . The share of
offshoring or globalization depends on the underlying business
needs and on what software is being developed. For instance,
while distributed development of IT applications is fairly
easy, embedded software and system development still faces
major challenges when adopting distributed development. An
 
 
industry panel at recent ICGSE showed that only 30% of all
embedded software is developed in a global or distributed con-
text, while the majority is still developed in co-located setups
 . Similarly, the amount of quality deficiencies and call-
backs across industries has increased in parallel to growing
global development and sourcing.
This paper provides an overview and longitudinal research
of all ICGSE conference instances since the start of this
conference series in 2006. It looks back at the topics addressed
and their evolution over time, but also studies the knowledge
transfer from Software Engineering research towards industrial
practice. We analyzed all published conference papers of
the ICGSE conference series covering 10 years of research
and industry collaboration thus digesting best practices and
industry state-of-the-practice in GSE and distributed projects
to answer the following research questions:
 
 
RQ 1 What are the main fields of interest reported in the
ICGSE conference series and how did these themes
evolve over time?
RQ 2 What maturity and impact do the themes addressed by
the ICGSE publications have?
RQ 3 What trends can be found in the ICGSE conference
series and industrial experience to shape future GSE
research?
 
 
The present paper summarizes experiences from academia
and industry to facilitate knowledge and technology transfer.
An outlook shows current trends in GSE to lay the foundation
for research as well as practical guidance for industry, as
distilled from many best practices.
The remainder of the paper is structured as follows: Sec-
tion II describes the study design for analyzing the ICGSE
publications. In Sect. III, we provide the results of analyzing
the papers published in 10 years of ICGSE and answer the
aforementioned research questions. In Sect. IV, we provide
both, a discussion of GSE’s state-of-the-practice in industry in
combination with further studies related to the present paper.
We conclude the paper in Sect. V.
 
 
 # II. STUDYDESIGN
To carry out the research presented in the paper at hand,
we utilized thesystematic reviewinstrument as described by
Kitchenham and Charters   and thesystematic mapping
studyinstrument as described by Petersen et al.  . Due
 

Category Description
Opinion personal opinion whether a certain technique is good
or bad, or how things should be done, not grounded in
related work and research methodology
Solution solution for a problem is proposed (or a significant
extension), application is demonstrated by example or
student labs; also includes proposals complemented by
(only) one case study for which no long-term evaluation
plan is obvious; demonstration is possible by argu-
mentation; note: this category also includes “validation
papers” (mainly example- or lab-based work)
Philosophical new way of looking/thinking, structuring a field in form
of a taxonomy or a framework, secondary studies like
SLR or SMS; note: “new way of...”includes transfer
research, i.e., approaches/practices used in one domain
that are applied and evaluated to another one
Evaluation implemented in practice (implementation), evaluation of
implementation conducted (implementation evaluation);
requires more than just one demonstrating case study
Experience (personal) experience, how are things done in practice;
can be either the very personal experience of an author
or an industrial experience report
 
to the nature of the presented study, we deviate in the data
collection procedures and study selection procedures: As data
source, we used the ICGSE conference proceedings, which
are available from the IEEE Digital Library^1. In total, the
ICGSE proceedings comprise 260 papers, which are full-,
short-, industry-, and education-related papers. Note, we opted
for conference “main track” papers only, i.e., PhD symposium
papers, as well as posters and tutorial- or workshop papers
were not included for analysis. Eventually, all papers were
downloaded and metadata were collected in a spreadsheet for
further analysis. In the following, we provide details about the
data analysis procedures.

 # A. Schema Development

As a first step, we selected the schemas to be utilized in
the analysis. We opted for a mixed approach in which we rely
on (quasi-)standard schemas and also on dynamic schemas
crafted from the set of publications analyzed.
As (quasi-)standard schemas, we selected theresearch type
facet(RTF) as described by Wieringa et al.  , thecon-
tribution type facet(CTF) as for instance used by Petersen
et al.  , and, eventually, we selected therigor-relevance
modelas proposed by Ivarsson and Gorschek   to get an
impression about the quality and relevance of ICGSE research.
The Tables I, II, and III provide a brief summary of the
respective criteria and/or scores.
Beyond these (quasi-)standard criteria and in order to get
more insight into the ICGSE publications, we also developed
two study-specific schemas. Using a Word Cloud as instru-
ment, we conducted a cluster analysis to work outthemes,

(^1) All ICGSE conference proceedings are available from [http://ieeexplore.](http://ieeexplore.)
ieee.org/servlet/opac?punumber=1001266.
TABLE II
CONTRIBUTION TYPE FACET AS USED BYPETERSENETAL.  .
Category Description
Theory construct of cause-effect relationships
Model representation of observed reality by concepts after
conceptualization
Framework frameworks/methods related to GSD, for instance
maturity or organization models that include meta-
models, models, and methods to apply them
Guideline list of advices, recommended best practices/success
factors if grounded in empirical evidence
Lessons Learned set of outcomes from obtained results, for instance
findings obtained from (comparative) case studies
Advice recommendation (usually from opinion without em-
pirical justification)
Tool a tool (focus: tool), if there is a tool as one building
block of a more comprehensive method/framework
only, then ”framework” is to be chosen
TABLE III
RIGOR-RELEVANCEMODEL ACCORDING TOIVARSSON,GORSCHEK .
Category Description
Rigor (scores: description is strong: 1, medium: 0.5, weak: 0)
Context described context of the study
Study design described reproducible study design incl., e.g., variables,
measures, etc.
Validity discussed threats to validity are classified and discussed
Relevance (scores: contributes to relevance; yes: 1, no: 0)
Subjects subjects used are representative
Context actual context is representative
Scale research is of “realistic” size
Research method research methods supports investigation in a
realistic setup, i.e., “real” situations
i.e., lists of topics addressed by the published papers. Figure 1
shows the Word Cloud used to derive the themes^2.
Fig. 1. Top thirty topics addressed in one decade of ICGSE.
Eventually, we found 15 clusters (see Table V) that we used
to categorize the papers by their contributions. Note that one
(^2) Note:In the cluster analysis, we removed words without added value,
such as GSE, GSD, global, software, engineering, development. We also
replaced plural words with the singular forms when both occurred in the
top thirty list.
 
Score Description
Strength of Evidence (scores: NA/NR=0,...,3)
NA/NR not relevant (e.g., position paper) or based on experience
only, e.g., “success stories” without empirical evidence
Weak university lab with students only/experiment or simulation
Average industry is involved, but only 1 case, such as a demon-
strator, or secondary studies, due to inherent publication
bias
Strong multi-case, longitudinal or replication studies (can be lab-
only or with industry involvement)
Industry Collaboration Pattern (scores: NA=0,...,3)
NA no involvement, e.g., university lab only or SLR/SMS
Interview practitioner interviews only
SingleCase single case (with/without complementing interviews)
Close e.g., multiple studies in 1 company, or multiple companies
in 1 study, or different research methods applied (mixed-
method)
 
paper can address one or more themes, which we also use to
study relationships among different topics.

The second study-specific schema is a maturity index, which
consists of two components (Table IV): the first component
is thestrength of evidenceto work out how the research
(part) was conducted, e.g., are results reported by a paper
coming from a “one-shot” student lab or a long-term industry-
hosted investigation. The second component is theindustry
collaboration patternto work out how industry is involved in
research. This model has some similarities to the aforemen-
tioned rigor-relevance model, but has a slightly different focus,
as this model also allows research to be of high relevance,
even though industry is not involved in the research (e.g.,
ground-breaking rigorously researched theories). Finally, both
components were used to compute the two “maturity indexes”
per theme (th):

withcatdenoting the different scores of either the strength
of evidence or industry collaboration pattern. For instance, if
we compute the index for theindustry collaboration pattern,
we selectcat={NA,Interview,SingleCase,Close}andwcat
assigns the weights for the categories withwNA =0. 1 ,
wInterview=0. 25 ,wSingleCase=0. 5 , andwClose=1. 0 .To
rate the relevance of a theme,ypubdenotes the number of
years in which papers on a theme were found in the ICGSE
proceedings from the past 10 years, i.e., we expect highly
relevant themes having a more frequent publication rate.

The index results in a number, and we consider a theme
the more “strong” or relevant for bigger numbers. After initial
test runs, we set the following threshold: a theme is considered
well-researched and highly relevant for industry collaboration

 
Fig. 2. Number of published papers (main conference) per ICGSE instance,
and addressed topics by year (and in total).
 
 
if the respective index is≥ 0. 4. The results of this evaluation
is summarized in Table V.
 
 
 # B. Data Analysis
Data analysis was conducted on the papers’ full text. For
every paper, the paper was downloaded, the metadata (title,
abstract, etc.) was collected, and the classification schemas
were iteratively applied. When all the data was available,
Microsoft Excel was used to generate descriptive statistics and
to perform computations, e.g., for the rigor-relevance model or
the maturity indexes. The data obtained from the classification
and the computations was then compared to the information
gathered from the simple headcount as used in   to confirm
initially found trends.
 
 
 # C. Validity Procedures
To improve the validity of our findings, as a first measure,
we relied on (quasi-)standardized classification schemas to
follow a well-accepted and proven approach. To complement
these standard schemas with study-specific schemas, we used
an iterative and tool-based approach to craft these schemas. All
analysis and classification steps were carried out iteratively
with continuous quality assurance. Finally, as we rely on a
specific pre-defined dataset, we addressed a potential reviewer
bias by avoiding a manual paper selection.
 
 
 # III. ANALYZING10 YEARS OFICGSE EXPERIENCE
For more than a decade, ICGSE aims at bringing together
researchers and practitioners to discuss GSE-related problems
and solutions. We therefore analyzed the 260 published confer-
ence papers for the topics of interest and for the contributions
made over time. In this section, we start by giving an overview
of the different themes addressed by the analyzed papers over
 

Fig. 3. Overview of the research type facets (left) and the contribution type facets (right) over time.
time. In Sect. III-A and in Sect. III-B, we provide a first
trend analysis by inspecting the field’s development using the
standard classification schemas. In Sect. III-C, we analyze the
impact ICGSE research had over time and work out those
themes that gained much attention/are perceived of special
relevance/importance to the community. The following section
contains both, the presentation of the data and a brief in-place
discussion/interpretation where applicable.
A. ICGSE Themes
Figure 2 illustrates the themes addressed by the ICGSE
publications over time. We used a heat-map-like visualization
to color-code the frequency of mentions and to identify the
champions among the themes.
The illustration shows the topicsProject Management,
Collaboration and Teams, andProcess and Organizationof
particular interest. In fact, having a more detailed look into
the respective papers, we find the general management topics
most frequently researched, e.g., project governance, risk man-
agement, estimation, collaborative work in teams (incl. task
allocation), organization capability improvement, and process
transition.
While “normal” Software Engineering challenges have been
discussed for years, ICGSE adds distribution as extra dimen-
sion thus calling for investigating problems and respectively
proposed solutions in a global context. For example, agile
and lean practices, which are considered the most promising
approaches to improve software development speed and qual-
ity are increasingly discussed; closely related to questions of
collaboration and team organization, as agile principles, such
as on-site customer, direct communication, or shared code
ownership have to be adopted to GSE. In the pool of the
ICGSE papers we hence found several papers investigating the
options to successfully enact agile approaches in GSE; quite
often supported by tools, such as Instant Messaging, different
collaboration tools, or collaborative testing and debugging.
Another aspect—especially in agile software development—
istrust. We found 16 papers (e.g.,  – ) making trust as
a key theme a first-class citizen of the discussion as part of
team-, culture-, and sourcing-related contributions.

Fig. 4. Overview and refinement of philosophical papers over time.
B. Development of the Field over Time
While Fig. 2 gives an initial overview of the themes ad-
dressed and their frequency over time, we use the different
classification schemas to carry out a more in-depth analysis
of the field’s development over time.
In Fig. 3, we provide a summary of the CTFs/RTFs
addressed by the ICGSE papers over time. The CTF part
underlines the aforementioned finding that ICGSE to a large
extent fosters knowledge transfer from “classic” SE to GSE.
The chart shows the majority of the papers being classified
asguidelinesandlessons learned. The RTF part allows for
rating the general maturity of the research field. The figure
shows two relatively stable trends over time: first, from the
very beginning on, ICGSE papers provide evidence based
onevaluationresearch andexperiences. Second, ICGSE has
a stable share of papers that are classified asphilosophical
papers, which, among other things, aim to discuss and/or
compare given/new concepts from different angles.
In order to better analyze these papers, we introduced
three sub-categories, namelySLR/SMSto collect all secondary
studies,Transferto select those studies that transfer a known
concept from SE to GSE, and Discussionto select those
papers discussing (G)SE problems and to offer/rate different
solution approaches. Figure 4 shows that secondary studies,
which mostly address aggregating and structuring reported
knowledge, account for 19% of the philosophical papers, i.e.,

 
the majority addresses the knowledge transfer and discussion
of solutions. This, again, underlines the significant work the
ICGSE community performs to transfer, apply, and analyze
SE concepts in the GSE context.

Regarding the maturity of the different contributions pub-
lished at ICGSE, Fig. 5 provides a systematic map illustrating
the achieved research maturity of the particular papers. The
map shows again the strong focus on collecting lessons learned
and providing guidance. In particular, lessons learned (
papers, 50%) are the largest share in the result set, and
furthermore experience-based lessons learned account for the
largest category of papers in the whole result set (50 papers,
19.2%). Hence, the map shows a fairly mature field in terms
of guidelines and experiences. However, on the other hand,
the map also shows missing theories on GSE (a trend that is
quite common to Software Engineering and its sub-disciplines
in general), but also some effort in developing models (e.g., to
better predict risk, quality, impact of team/distribution pattern,
and so forth). Finally, the map shows that individual advice
(not grounded in hard evidence) is not present at all, and the
map shows that the community is also proposing different
tools that help improving collaboration and communication
in distributed projects.
The previously presented charts indicate a certain devel-
opment over time, which is also reflecting the evolving in-
dustry needs enforced by changing markets and technologies.
The set of analyzed papers contains a number of examples
illustrating this evolution. For instance, the ICGSE paper pool
comprises different models synthesized from different litera-
ture, research, and practitioner-related sources. For example, a
Global Teaming Model  –  provides a structured best-
practice-based guideline to set up and run distributed projects,
or a Survivability Model  ,   that helps analyzing
and improving different actions taken in GSE projects. Both

 
exemplarily selected models emerge from long-term research
and collaboration, as indicated by the references. Furthermore,
different secondary studies (systematic literature reviews and
mapping studies) aim to structure the GSE domain with
the purpose to structure the current state-of-the-practice and
to derive different success factors and guidelines supporting
effective GSE project set up and operation, such as  – .
Finally, the ICGSE papers are to a large extend grounded in
applied research in which many companies are involved in
GSE (e.g., Siemens, Alcatel, Ericsson, Microsoft, and also
many small and medium enterprises, such as  – ).
 
 
 # C. Relevant ICGSE Themes and their Impact
As just found the previous section, the research quality
of the ICGSE papers is mainly driven by evidence-based
research, and the evidence presented is, to a large extend, col-
lected in academia-industry collaboration. To inspect this trend
suggested by the systematic map in Fig. 5, we applied our
custom schema. Figure 6 illustrates thestrength of evidence
and theindustry collaboration patternover time. The figure
shows (and thereby confirms the interpretation of Fig. 5) the
large share of research categorized asaverage-strong.Atthe
same time, the figure shows the high share of close industry
collaboration.
 
Fig. 6. Overview of the strength of evidence and the industry collaboration
pattern over time.
 
 
To better (reliably) rate the impact of the research published
at ICGSE, we applied two models. The aforementioned model
addressing strength of evidence and industry collaboration pat-
tern is complemented by the rigor-relevance model. For both
models, in Fig. 7 and Fig. 8, we use the same visualization to
investigate the relevance of ICGSE research for industry.
The figures show that, according to the rigor-relevance
model (Fig. 7), 74 ICGSE papers are considered highly rele-
vant, and of those, 29 also meet highest requirements regarding
the scientific rigor. Although the applied criteria differ, the
study specific model in Fig. 8 shows similar trends: 108 papers
 



emerge from a close industry collaboration, and of those, 54
provide strong evidence. This analysis shows the relevance of
the ICGSE papers and and their solid foundation in evidence.
Based on the classifications and on the ratings regarding
strength of evidence and industry collaboration pattern, we
revisited themes with purpose to identify those themes that
have a mature research and those with close industry collabora-
tion to eventually conclude the most relevant GSE topics. The
results shown in Table V provide two insights: first, the table
outlines the mature and relevant themes, and second, the table
also shows those topics that are, from the GSE perspective,
“under-researched” thus showing routes for future research^3.
In particular, from the research perspective, communica-
tion and soft skills, project management, agile, collaboration
and teams, process and organization, sourcing and supplier
management, quality, and success factors are well researched.
From the perspective of the industry relevance, agile, col-
laboration, process, sourcing, quality, and success factors
are researched in close collaboration. That is, collaboration,
process, sourcing, and success factors have to be considered
the major themes in ICGSE (with highest research maturity
and biggest impact to industry).
Compared to Fig. 2, this rating draws a slightly different
picture. From the simple headcount, project management was
the champion. However, Table V states project management

(^3) As already mentioned in Sect. II-A, we initially set the thresholds for
SoE and ICP to 0.4 to define a baseline. This baseline can however change
over time when more in-depth information regarding the actual impact of the
different ICGSE contributions is available. This baseline as “artificial” number
will also serve the scoping of research activities, e.g., project management is
well-researched yet lacking practical confirmation, or agile is of high relevance
to industry yet lacks some more research. Furthermore, this baseline will also
help to confirm, e.g., whether well-researched topics really impact practice
(and how). Therefore, Table V provides an initial evaluation, which can be
used by further researchers to fill the gaps (e.g., in project management,
agile, or quality), or to replicate studies and confirm findings (e.g., sourcing,
collaboration).

Fig. 8. Evaluation of the ICGSE papers regarding their strength of evidence
and industry collaboration pattern.
a well-research topic with yet little industry involvement. The
same holds for the topic agile, which is present in the result set
with strong industry involvement, yet lacking strong evidence.
Another finding, which just became obvious in Fig. 2, is the
low number of papers addressing testing. Actually, testing was
perceived as one of the core software development activities
suitable for outsourcing. However, the numbers obtained from
analyzing the ICGSE papers do not confirm this conventional
wisdom (similarly to architecture and design, and require-
ments engineering). Therefore, the data shows that ICGSE
achieved a certain maturity in selected topics, and the majority
of these topics deals with the organization of distributed
projects, the empowerment of distributed teams, and barriers
and success factors mostly coming along with collaboration and communication across global and cultural distance. More
engineering-related topics, such as design or testing are not
yet comprehensively addressed in the ICGSE papers.
In a nutshell, the ICGSE publication body shows a signifi-
cant impact to industry. A considerable share of ICGSE papers
is grounded in academic-industry cooperation in which con-
cepts and new approaches, methods, and tools are disseminated
and evaluated in practice  ,  ,  .

 # IV. INDUSTRYSTAT E-OF-THE-PRACTICE
After having analyzed the big picture of GSE topics and
themes and their evolution over time, we provide some practi-
cal lessons learned. In this section, we collect and summarize
industry state-of-the-practice in GSE. As a basis, we take the
previously discussed ICGSE articles from the past decade and
aggregate them into meaningful clusters of relevance. Results
stem from companies with a published track record in GSE,
such as Siemens, Alcatel, Ericsson, Microsoft, but also many
small and medium enterprises (see for instance  – ).
We also ground our discussion in the feedback collected from
research and industry, as for instance collected in discussions
at the different panels of recent ICGSE conferences.

 # A. Drivers for Going Global

Offshoring and outsourcing are two dimensions in the scope
of globalized software development. They do not depend on
each other and can be implemented individually. All GSE
formats allow for a more flexible management of operational
expenses, since resources are allocated at places and in regions
where it is most appropriate to flexibly fulfill needs and con-
stantly changing business models  . Figure 9 summarizes
the reasons for GSE based on data from software companies
in Europe and North America  ,   (and complemented with
further findings, e.g., from  – ). 
Cost reduction is still the major trigger for globalization,
even though its relevance has been decreasing over time. This
reasoning is simple and yet so effective that it is mainstream
for most companies and media today. Labor cost varies around
the globe. For similar skills and output, companies pay a

 
different amount of money per work unit in different places.
Looking to mere labor cost for comparable skills of educated
software engineers, several Asian countries have a rate of 10-
40% of what is paid for the same work in Western Europe
or USA. Salary differences theoretically allow reducing R&D
labor cost by 40-60%  – ,  . However, missing and
insufficient competences, hidden costs, and extra overheads
severely reduce this potential  .
 
 
 # B. Going Global: Risks and Chances
While market proximity, cost advantages, and skill pool are
still considered beneficial, still, GSE bears risks coming on
top of normal project risks  ,  :
 
- 20-40% extra cost at begin of learning curve for 1-2 years
- Over 20% of sourcing contracts are cancelled in first year
- Over 50% of the projects do not deliver according to
    objectives or strategy and are cancelled downstream
- Over 80% of companies are not satisfied with their global
    software activities
- Increasing unexpected loss of intellectual property rights
    (IPR) and technology know-how
- Decreasing proficiency level due to inexperienced hiring
As companies jump on GSE, they find the process of devel-
oping and launching new products and services increasingly
complex, as they have to integrate skills, people, and processes
scattered across different sites. If not sufficiently prepared,
after a while, many companies realize that savings are much
smaller than expected and problems are more difficult to cure
than before  ,  ,  . Therefore, disillusioned many
companies stop their engagement in GSE. The ICGSE industry
panel showed that around the globe 20-25% of all outsourcing
relationships fail within the first two years and 50% fail within
five years  ,  . This is supported by studies reporting a
trend towards localization and insourcing  ,  .

 
 # C. Reasons for GSE Failure
Globally distributed projects often fail when tasks were bro-
ken down into too small chunks, e.g., asking a remote engineer
to verify software concurrently developed at another site  . In
such cases, distance and lacking direct communication hinder
development activities. Communication across project sites is
the most remarkable barrier for outsourcing and offshoring.
That is, inefficient communication hinders both coordination
and management processes. The GSE-related challenges and
major reasons for project failure can thus be summarized as
follows  ,  – ,  ,  ,  ,  :
 
- Project delivery failures
- Insufficient quality
- Distance and culture clashes
- Staff turnover
- Poor supplier services
- Instability with overly high change rate
- Insufficient competences
- Wage and cost inflation
- Lock-in
- Inadequate IPR management.


 # D. The Cost of GSE

So far, big savings in GSE have been reported only from
(business) processes which are well defined and already per-
formed before offshoring started, and which need not much
control  ,  . This includes maintenance projects (given
that the legacy software has some sort of description) where
some or all parts could be distributed, technical documentation
(i.e., creation, knowledge management, packaging, translation,
distribution, maintenance), or validation activities. Develop-
ment projects have shown good results in those cases where
tasks have been separated to provide distributed teams with
ownership and clearly defined goals  , yet, some overhead
is to expect from distributed projects  .
Considering these challenges, actual cost reduction from
GSE is much less than the expected potential savings of 40-
60% if the same process is split across the globe with changing
responsibilities  ,  ,  . Successful companies report a
10-15% cost reduction after a 2-3 year learning curve and,
initially, outsourcing might add up to 20% extra efforts. The
learning curve for transferring a whole software package to a
new team (e.g., location) takes about 12 months  ,  ,  .
For instance, the learning curve for effectiveness in software
design and coding allows for reaching 50% effectiveness
after 1-3 months and 80% after 3-5 months. The speed also
depends on process maturity and technology complexity (yet,
the actual process applied seems to be of little impact  
and is often selected in non-systematically anyway  , but
a process transition offers benefits and bears risks  ). Each
of the following bullets accounts for a 5-10% increase of cost
compared to regular onshore cost in the home country  ,  :

- Supplier and contract management
- Coordination and interface management
- Fragmented and scattered processes
- Project management and progress control
- Training, knowledge management, communication
- IT infrastructure, global tools licenses
- Liability coverage, legal support.

 # E. Best Practices for Mitigating GSE Risks

Risk management is the systematic application of man-
agement policies, procedures and practices to the tasks of
identifying, analyzing, evaluating, treating, and monitoring
risk. Global development projects pose specific risks on top of
regular risk repositories and check lists (Sect. IV-B). Looking
to the articles of the past 10 ICGSE conferences dealing with
different risk mitigation strategies (e.g.,  ,  – ), we
distilled a framework of nine best practices to mitigate the
GSE risks. Figure 10 shows nine factors, which had highest
appearance rate in all articles, grouped in a 3 × 3 matrix where
these nine techniques are mapped to three success factors
(competences, communication and collaboration) and three
benefits (flexibility, innovation and efficiency).

 # V. CONCLUSION AND TRENDS
In this paper, we analyzed 10 years of ICGSE, and we
looked for the themes addressed in the past decade, accumu-


lated knowledge, and trends. We complemented our analysis
with a discussion of the current state-of-the-practice, which is
grounded in recently published studies and discussions from
the various panels of the ICGSE conference. The analysis
of the ICGSE papers revealed that the ICGSE conference
series addresses both conducting high-quality research, but
also fostering the transfer of established Software Engineering
concepts, methods, practices, and tools to the GSE context.
Among 15 themes that were defined using a cluster anal-
ysis, Collaboration and Teams, Processes and Organization,
Sourcing and Supplier Management, and Success Factors were
identified as well-researched with high relevance to industry.
We conclude that research reported at ICGSE addresses the
organization of distributed projects and the success factors and
barriers to care about the most. However, beyond these more
organizational aspects, the ICGSE community also works on
concepts and tools to support the transition from “classic”
SE to GSE, and the community puts significant effort in
collecting, aggregating and structuring knowledge, which is to
a large extent grounded in applied research and which helps
companies mastering GSE.
 
 
 # A. Limitations
The present study has some limitations that need to be
discussed. In particular, the study at hand utilized the well-
known instruments for conducting secondary studies, reused
proven classification schemas, and followed rigorous methods
to analyze and report data. However, as the study is focused on
the ICGSE publication pool only, we cannot claim to present
the full picture, as we did not include further publications in
our study, e.g., journal articles or conference papers published
at other venues. Another limitation is the foundation of our
analysis in literature and selected open discussions only. This
also affects the notion of rigor, relevance, and impact. All
numbers and classifications presented in this paper have to
be handled with care, as our classification can only pro-
vide indication. Yet, it remains unknown whether the present
classification reflects the actual situation in practice properly.
Interviews or other more structured forms of expert-based
information gathering was not employed in this study, but
 

would be necessary to confirm the findings present in the paper
at hand. Those limitations however motivate further research
(for which our current classification and ranking provides the
first baseline) to round out a more comprehensive picture in
future.

 # B. Implications and Future Development of GSE

Global Software Engineering will evolve towards a standard
engineering management method, which must be mastered by
every R&D manager. Processes and product components will
increasingly be managed in a global context. Suppliers from
many countries will evolve to ease setting up and operate
GSE even for small and mid-sized enterprises in the high-
cost countries. Brokers will emerge that help finding partners
in different parts of the world and managing the offshoring
overheads. However, working in a global context obviously
has advantages but also drawbacks. While the positive side
accounts for time-zone effectiveness (as for instance claimed
by the Follow-the-Sun paradigm  ,  ) or reduced cost
in various countries, we should not close our eyes in front
of risks and disadvantages (Sect. IV-B). The business case of
working in a low-cost country is surely not a simple trade-
off of different cost of engineering in different regions. Many
companies struggle because they just looked to the perceived
cost differences in labor cost, but not enough on risks and
overhead expenses coming along with the more complex
project organization. Approximately 20% of all globalization
projects are cancelled within the first year, and about 50% are
terminated early. In many cases, the promise of savings has
not matched the diminishing returns of unsatisfied customers.
Many factors cannot be quantified or made tangible initially,
but will sooner or later heavily contribute to the overall
performance, and practitioners recognize the difficulties. There
is a simple rule:Only those who professionally manage their
distributed projects will succeed in the future.
Furthermore, it needs to be taken into account that cost
per headcount will stay low for few years, but will steadily
increase in future due to rising living standards in the emerging
countries contributing to GSE’s growth:GSE has a strong
contribution in improving living conditions around the world.
Bridging the divide is best approached by sharing values
and understanding of culture, which is constantly subject
to discussion at ICGSE as well, e.g.,  ,  . Increasing
standards of living in China, India and many other of today’s
low-cost countries will generate hundreds of millions of new
middle class people with an increased demand for more IT.
The journey has begun, but it is far from being clear where
it will end. Clearly, some countries will come to saturation,
as GSE essentially means that all countries and sites have
their fair chance to become a player and compete on skills,
labor cost, innovativeness, and quality. Software Engineering
is based upon a friction-free economy with any labor being
moved to that site that is best suited regarding the actual
constraints. No customer is anymore in a position to judge
that a piece of software from a specific site is better or worse
that software produced somewhere else in the world. In a nut-

 
shell, the old-economy labeling of “Made in [country x]” has
become legacy thinking not applicable to software industries.
What counts are business impact and performance, such as
resource availability, productivity, innovativeness, quality of
work performed, cost, flexibility, skills, and the like.
