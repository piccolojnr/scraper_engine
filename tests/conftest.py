from __future__ import annotations

import pytest

from app.extractors.utils import parse_html


@pytest.fixture
def sample_html() -> str:
    return """
    <html>
      <body>
        <!-- comment to strip -->
        <div class="content">
          <h1>  Admission   Info  </h1>
          <p class="intro">Welcome <strong>students</strong>.</p>
          <ul id="programmes">
            <li>BSc Computer Science</li>
            <li>BSc Mathematics</li>
          </ul>
          <a class="doc" href=" /docs/prospectus.pdf ">Prospectus</a>
          <div class="tags" data-tags="science admission"></div>
          <div class="wrapper">
            <table id="fees">
              <tr><th>Programme</th><th>Fee</th></tr>
              <tr><td>BSc CS</td><td>1000</td></tr>
              <tr><td>BSc Math</td><td>900</td></tr>
            </table>
          </div>
        </div>
      </body>
    </html>
    """


@pytest.fixture
def nested_table_html() -> str:
    return """
    <html>
      <body>
        <section class="table-container">
          <div>
            <table>
              <tr><th>Item</th><th>Value</th></tr>
              <tr><td>Deadline</td><td>30 Sep</td></tr>
            </table>
          </div>
        </section>
      </body>
    </html>
    """


@pytest.fixture
def sample_soup():
    return parse_html(
        """
    <html>
      <body>
        <!-- comment to strip -->
        <div class="content">
          <h1>  Admission   Info  </h1>
          <p class="intro">Welcome <strong>students</strong>.</p>
          <ul id="programmes">
            <li>BSc Computer Science</li>
            <li>BSc Mathematics</li>
          </ul>
          <a class="doc" href=" /docs/prospectus.pdf ">Prospectus</a>
          <div class="tags" data-tags="science admission"></div>
          <div class="wrapper">
            <table id="fees">
              <tr><th>Programme</th><th>Fee</th></tr>
              <tr><td>BSc CS</td><td>1000</td></tr>
              <tr><td>BSc Math</td><td>900</td></tr>
            </table>
          </div>
        </div>
      </body>
    </html>
    """
    )


@pytest.fixture
def nested_table_soup():
    return parse_html(
        """
    <html>
      <body>
        <section class="table-container">
          <div>
            <table>
              <tr><th>Item</th><th>Value</th></tr>
              <tr><td>Deadline</td><td>30 Sep</td></tr>
            </table>
          </div>
        </section>
      </body>
    </html>
    """
    )
